# Design

## The question

One published policy, one applicant, one answer:

    which required leaves does this evidence demonstrate, and what is the cheapest
    set of leaves still missing?

And one more, because the answer is only worth anything if the policy cannot move underneath
it:

    which sealed version of the policy was this decided on, and is it still the current one?

The policy is a tree the owner publishes on chain. The evidence is prose. The contract
bridges them with a model that is only allowed to report leaves, and code that is the only
thing allowed to decide.

## The decision ladder

1. **Keyword floor.** A leaf may carry one literal keyword. Code folds the evidence
   (case, script variants, punctuation) and commits the leaf if the keyword appears as
   whole tokens. This is identical on every node and needs no model.
2. **Model layer.** The model is given the closed leaf vocabulary with its labels and the
   folded evidence, and answers with leaf codes plus a verbatim quote for each. Nothing
   else is a valid answer.
3. **Verification.** Code re-checks every code against the vocabulary and every quote
   against the folded text. A quote that is not in the text, a code outside the vocabulary,
   or a quote shorter than three tokens makes the whole reading unusable. One bad item is
   not dropped silently; the reading fails.
4. **Derivation.** The tree of the sealed version the assessment is bound to is evaluated
   against the agreed leaves. AND nodes need every child. OR nodes need any child. An
   unsatisfied OR node reports the cheapest branch, so the answer is a repair plan rather
   than a list of everything wrong.

## Versioning

A verdict is a statement about a tree. If the tree can change while the verdict stands, the
verdict becomes a lie, so the tree is versioned and the version is part of the record.

    policy_version   the version being edited, or the last sealed one
    policy_open      1 while the current version accepts edits, 0 once sealed
    version_tree     version -> canonical tree, written once by seal_policy()
    node_added       code -> the version that created the node

The lifecycle is deliberately narrow:

    open (version 1, editable)
      add_group / add_item ...
      seal_policy()      -> canonical tree stored, policy_open = 0, edits now revert
      assess(case)       -> allowed only while policy_open == 0, record bound to version 1
      open_policy()      -> version 2, editable again; version 1 stays as it was
      add_group / add_item ...
      seal_policy()      -> version 2 stored; version 1 is still readable through tree_of(1)

Nodes are never edited or removed. A node created in version 2 simply does not exist in
version 1, because every read of the tree goes through `_in_version(code, version)`, which
compares `node_added`. That is what makes `tree_of(1)` reproducible forever without keeping
a second copy of the tree.

The effective policy at any moment is the newest **sealed** version. While a draft is open
it is invisible to the gate: `assess()` reverts with `POLICY_NOT_SEALED` and existing
verdicts stay current, because nothing has been published yet.

## Records

Assessments are stored per case and per version, keyed `case@vN`, and are never overwritten:

    rec_verdict   "case@vN" -> ELIGIBLE | MISSING | UNUSABLE
    rec_met       "case@vN" -> leaves demonstrated, sorted
    rec_missing   "case@vN" -> cheapest repair, sorted
    rec_counts    "case@vN" -> "<demonstrated>,<still needed>"
    case_latest   case id   -> version of its newest record
    cases         distinct case ids
    assessments   records written

Two consequences follow, and both are the point:

- **The gate fails closed.** `is_eligible` requires a stored `ELIGIBLE` **and** that the
  record's version equals the newest sealed version. A policy edit therefore closes the
  gate on every earlier verdict, and `is_stale` says which ones.
- **Nothing is lost.** Assessing the same case under a newer version appends a record.
  `verdict_of` follows the newest, `verdict_at` reads one version, and `history_of` returns
  the whole chain of decisions as `v1:ELIGIBLE|v2:MISSING`.

Re-assessment is not a refresh of an old verdict: it is a new decision, on a named tree,
with its own evidence check. The previous decision remains visible.

## State

    policy
      node_mode      code -> AND | OR | ITEM
      node_parent    code -> parent code, "" for the root
      node_label     leaf code -> human label, the only thing the model sees
      node_keyword   leaf code -> folded keyword, may be empty
      node_added     code -> policy version that created it
      node_index     registration order, comma joined
      nodes          u256 counter
      root           code of the single root, "" before it exists

    versions
      policy_version u256
      policy_open    u256
      version_tree   version -> canonical sealed tree

    cases and records
      case_text      case id -> evidence text, write once
      rec_*          "case@vN" -> verdict, met, missing, counts
      case_latest    case id -> newest record version
      cases, assessments   u256 counters

Every map is keyed by a validated ASCII code, and the only enumeration the contract does is
over `node_index`, which is a plain string. No `TreeMap` is ever iterated, so every node
sees exactly the same order.

## Registration invariants

The tree cannot be malformed after the fact, because the write path refuses to build a
malformed one:

- The current version must be open. After `seal_policy()`, `add_group` and `add_item`
  revert with `POLICY_SEALED`.
- A parent must already exist, and must be a group. A leaf cannot become a parent later,
  because a leaf's mode never changes.
- The first node added with an empty parent becomes the root, and a second root is
  refused. A parent-before-child rule makes a cycle impossible: a new node is not a
  parent of anything when it is created, so nothing can already point back to it.
- Codes are 2 to 24 characters of letters, digits, `-`, `_` or `.`, and are never reused.
- The tree is capped at 64 nodes, and a version is capped at 40 leaves **at construction**:
  `add_item` reverts with `TOO_MANY_LEAVES` on the 41st leaf. The reading step is bounded at
  40 leaves, so a policy it could not read cannot be built in the first place.
- `seal_policy()` refuses a tree with no root, no leaves, or a group with no children in
  that version (`NO_TREE`, `NO_ITEMS`, `EMPTY_GROUP`). A half-built policy can never be
  published, and `assess()` re-checks the same conditions before any non-deterministic work
  starts.

Cases are write-once per id, and a case is assessed at most once per version. A verdict is
a statement about one piece of evidence under one tree, not a value anyone can refresh in
place.

## Evaluation

`_evaluate(node, available, version)` returns `(needed, missing)`:

    ITEM   available -> (0, [])   otherwise (1, [code])
    AND    sum of children's needed, union of their missing lists
    OR     (0, []) if any child is satisfied, otherwise the child with the smallest
           (needed, code) and that child's missing list

For AND the union is the only repair. For OR the contract reports one branch: the branch
that costs the fewest leaves, with ties broken by the lexicographically smaller child code.
That tie-break is stated here because it is a policy choice, not a discovery. The result is
the minimum repair over the tree for unit leaf costs; it is not a claim that some other
policy would be easier to satisfy.

## Edges that are deliberate

- **An empty OR group** would be unsatisfiable and an **empty AND group** vacuously true.
  Both are refused at sealing and at assessment instead of being given a meaning.
- **A leaf with no keyword** depends entirely on the model. A leaf with a keyword can still
  be found by the model, and the union of both layers is what gets demonstrated.
- **An over-long model answer** is not cut down to size. More items than the bound allows is
  not a reading, so the case is `UNUSABLE`; a trimmed answer would silently drop a leaf.
- **A draft policy is not in force.** Opening version 2 and adding nodes changes nothing
  until it is sealed.
- **Missing is not failure to try.** `MISSING` names leaves; it never says why the applicant
  did not supply them.

## Threat model

**Hostile evidence.** The evidence is quoted into the prompt as untrusted data between
markers, with an explicit instruction that it is data. The structural defence is stronger
than the fence: a successful injection can only make the model report a leaf, and every
reported leaf must be backed by a span that code finds in the text. An applicant cannot
manufacture a leaf out of nothing, but an applicant whose evidence genuinely contains the
words can. The contract judges the text it is given, not the world.

**Hostile model.** The model cannot see the tree, the verdict rules, the case id, or any
other case. It can only add or omit leaves, and every omission is visible afterwards in
`missing_of`. A model that is confidently wrong is a false reading, not a false verdict:
the verdict follows from the leaves and the published tree.

**Hostile owner.** The owner can publish any tree, add keywords, and start a new version.
Every write is public and indexed, so a policy change is visible to everyone. What the owner
cannot do is move the ground under a verdict that already exists:

- a sealed version cannot be edited, so the tree behind a record is fixed;
- a new version closes the gate on every earlier verdict instead of silently re-scoring it;
- a stored verdict cannot be edited or deleted, and a case cannot be assessed twice under
  the same version.

The owner can still publish a policy that is unfair or trivially satisfied. That is a
statement about the owner, and it is readable on chain before anyone relies on it.

**Hostile applicant.** Registering a case is permissionless, so anyone can fill the case
ids. That is deliberate: the evidence is the applicant's statement anyway. A consumer that
needs a specific applicant should key its own record on the case id it expects.

## Limits

1. Leaves are boolean. There is no partial credit, no weighting and no scoring.
2. A keyword is a literal token match on folded text. It is a convenience for leaves that
   are unambiguous strings, not a semantic fallback.
3. The cheapest repair is computed against the sealed tree of one version. Satisfying the
   leaves it names makes that tree pass; it is not a statement about the applicant's real
   security posture.
4. One record per case per version. A wrong `UNUSABLE` cannot be retried under the same case
   and version; the applicant registers a new case id, or waits for a new version.
5. Old versions stay readable but are not re-evaluated. `tree_of(n)` is history, not a
   supported assessment mode.
6. Evidence is capped at 2,000 characters, so a long document must be excerpted. What is
   not quoted cannot be found.
7. The contract reads text only. It does not fetch, authenticate or timestamp anything.
