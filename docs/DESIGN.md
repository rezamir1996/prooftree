# Design

## The question

One published policy, one applicant, one answer:

    which required leaves does this evidence demonstrate, and what is the cheapest
    set of leaves still missing?

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
   against the folded text. A quote that is not in the text, a code outside the
   vocabulary, or a quote shorter than three tokens makes the whole reading unusable. One
   bad item is not dropped silently; the reading fails.
4. **Derivation.** The tree is evaluated against the agreed leaves. AND nodes need every
   child. OR nodes need any child. An unsatisfied OR node reports the cheapest branch,
   so the answer is a repair plan rather than a list of everything wrong.

## State

    policy
      node_mode      code -> AND | OR | ITEM
      node_parent    code -> parent code, "" for the root
      node_label     leaf code -> human label, the only thing the model sees
      node_keyword   leaf code -> folded keyword, may be empty
      node_index     registration order, comma joined
      nodes          u256 counter
      root           code of the single root, "" before it exists

    cases
      case_text      case id -> evidence text, write once
      case_verdict   case id -> ELIGIBLE | MISSING | UNUSABLE
      case_met       case id -> leaves demonstrated, sorted, comma joined
      case_missing   case id -> cheapest repair, sorted, comma joined
      case_counts    case id -> "<demonstrated>,<still needed>"
      cases          u256 counter

Every map is keyed by a validated ASCII code, and the only enumeration the contract does
is over `node_index`, which is a plain string. No `TreeMap` is ever iterated, so every
node sees exactly the same order.

## Registration invariants

The tree cannot be malformed after the fact, because the write path refuses to build a
malformed one:

- A parent must already exist, and must be a group. A leaf cannot become a parent later,
  because a leaf's mode never changes.
- The first node added with an empty parent becomes the root, and a second root is
  refused. A parent-before-child rule makes a cycle impossible: a new node is not a
  parent of anything when it is created, so nothing can already point back to it.
- Codes are 2 to 24 characters of letters, digits, `-`, `_` or `.`, and are never reused.
- The tree is capped at 64 nodes and the leaf vocabulary at 40, which bounds both the
  prompt and the evaluation.
- Assessment refuses a tree with no leaves, no root, or a group with no children, so a
  half-built policy can never produce a verdict. These checks run before any
  non-deterministic work starts.

Cases are write-once per id, and an assessed case is never reassessed. A verdict is a
statement about one piece of evidence at one time, not a value anyone can refresh.

## Evaluation

`_evaluate(node, available)` returns `(needed, missing)`:

    ITEM   available -> (0, [])   otherwise (1, [code])
    AND    sum of children's needed, union of their missing lists
    OR     (0, []) if any child is satisfied, otherwise the child with the smallest
           (needed, code) and that child's missing list

For AND the union is the only repair. For OR the contract reports one branch: the branch
that costs the fewest leaves, with ties broken by the lexicographically smaller child
code. That tie-break is stated here because it is a policy choice, not a discovery. The
result is the minimum repair over the tree for unit leaf costs; it is not a claim that
some other policy would be easier to satisfy.

## Edges that are deliberate

- **An empty OR group** would be unsatisfiable and an **empty AND group** vacuously true.
  Both are refused at assessment instead of being given a meaning.
- **A leaf with no keyword** depends entirely on the model. A leaf with a keyword can
  still be found by the model, and the union of both layers is what gets demonstrated.
- **Missing is not failure to try.** `MISSING` names leaves; it never says why the
  applicant did not supply them.
- **The gate fails closed.** `is_eligible` is true only for a stored `ELIGIBLE`, so an
  unknown case, an unusable reading and an unassessed case all read as false.

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

**Hostile owner.** The owner can publish any tree, add keywords, and change both at any
time before an assessment. Every write is public and indexed, so a policy change is
visible to everyone. The owner cannot edit a stored verdict, reassess a case, or remove a
leaf from history: `node_index` only grows.

**Hostile applicant.** Registering a case is permissionless, so anyone can fill the case
ids. That is deliberate: the evidence is the applicant's statement anyway. A consumer that
needs a specific applicant should key its own record on the case id it expects.

## Limits

1. Leaves are boolean. There is no partial credit, no weighting and no scoring.
2. A keyword is a literal token match on folded text. It is a convenience for leaves that
   are unambiguous strings, not a semantic fallback.
3. The cheapest repair is computed against this tree only. Satisfying the leaves it names
   makes the tree pass; it is not a statement about the applicant's real security posture.
4. One reading per case. A wrong `UNUSABLE` cannot be retried under the same case id; the
   applicant registers a new case.
5. Evidence is capped at 2,000 characters, so a long document must be excerpted. What is
   not quoted cannot be found.
6. The contract reads text only. It does not fetch, authenticate or timestamp anything.
