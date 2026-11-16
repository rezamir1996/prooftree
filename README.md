# ProofTree

An on-chain eligibility gate for evidence that arrives as prose. A published, versioned
AND/OR requirement tree, a model that may only name leaves it can quote, and code that
decides.

    evidence text  ->  [ model names leaves, code checks the quotes ]  ->  leaf set
    leaf set + sealed tree of one version  ->  AND/OR evaluation  ->  ELIGIBLE or the cheapest repair

If the tree is satisfied the verdict is `ELIGIBLE`. If it is not, the contract does not
just say "no": it returns the smallest set of leaves that would make it yes. If the reading
cannot be trusted the verdict is `UNUSABLE` and the gate returns `false`.

## Live on Studio

    contract       0x6f7dd17543b165847c301Dc21DAed004caFd2F9b
    explorer       https://explorer-studio.genlayer.com/address/0x6f7dd17543b165847c301Dc21DAed004caFd2F9b
    deploy tx      0xffedbe3ed25686d0906b2f54b2ce3a6e5d739a73910eeb3218835e798eee250f
    site_label     vendor-tree-v2

The tree published in version 1:

    qualified (AND)
      +-- soc2        a SOC 2 Type II report
      +-- enc (OR)
      |     +-- aes        encryption at rest with AES-256
      |     +-- hsm        keys held in an HSM or managed KMS
      +-- dpa         a signed data processing agreement

Two cases were registered and assessed against that sealed version, and both branches of
the decision are live:

| case | evidence shows | verdict | demonstrated | missing | counts |
| --- | --- | --- | --- | --- | --- |
| `vendor-a` | SOC 2 report, AES-256, signed DPA | `ELIGIBLE` | `aes,dpa,soc2` | - | `3,0` |
| `vendor-b` | SOC 2 report, signed DPA | `MISSING` | `dpa,soc2` | `aes` | `2,1` |

`counts_of` is `<demonstrated>,<still needed>`, and `is_eligible` was read back as `true`
for `vendor-a`, `false` for `vendor-b`, and `false` for a case id that was never
registered.

Two things to notice in the second row. `missing` reports `aes`, not `aes,hsm`: the OR
node is unsatisfied, and the contract names the cheaper of its two branches rather than
everything that fails. And `aes` in the first row was not found by the model at all - the
leaf carries the literal keyword `aes-256`, so the deterministic floor committed it.

Then the policy itself moved, which is the part that makes this a primitive rather than a
snapshot:

    seal v1  ->  both vendors assessed  ->  open_policy  ->  add leaf "pentest"  ->  seal v2

| read, after v2 was sealed | value |
| --- | --- |
| `verdict_of("vendor-a")` | `ELIGIBLE` - the stored record is untouched |
| `policy_version_of("vendor-a")` | `1` - it is bound to the tree it was decided on |
| `tree_of(1)` | unchanged, still on chain |
| `is_stale("vendor-a")` | `true` |
| `is_eligible("vendor-a")` | `false` - the gate fails closed |

Assessing the same case again under version 2 adds a second record instead of overwriting
the first:

    verdict_of("vendor-a")     MISSING      missing "pentest"     counts 3,1
    history_of("vendor-a")     v1:ELIGIBLE|v2:MISSING
    verdict_at("vendor-a", 1)  ELIGIBLE

Addresses, all sixteen transaction hashes, validator votes and every state read are in
[`EVIDENCE.md`](EVIDENCE.md).

## Why this needs an Intelligent Contract

Evidence arrives as prose. "We hold a SOC 2 Type II report covering the production
environment" and "audit completed under AICPA standards" may or may not be the same
requirement, and no regular expression decides that. The reading step is semantic, so it
needs a model - and a model deciding whether a vendor is qualified is exactly the decision
that one party must not take in private.

So the model is given one narrow job: report which registered leaves the evidence
demonstrates, each backed by a span copied verbatim from the evidence. It never sees the
tree, the verdict words, or the meaning of an OR. The policy is published on chain by the
owner, sealed into an immutable version, and turning an AND into an OR is an on-chain
write that anyone can read.

## The versioned policy

A verdict only means something against the tree it was decided on, so the tree is versioned
and every verdict carries its version:

1. The owner edits an open version. Nodes are append-only and record the version that
   created them.
2. `seal_policy()` closes the version and publishes its canonical form (sorted by code, so
   write order does not matter). Edits then revert with `POLICY_SEALED`.
3. `assess()` refuses to run unless the current version is sealed, and binds the record to
   that version.
4. `open_policy()` starts the next version. Sealed versions are never edited again, so
   `tree_of(1)` keeps returning exactly what version 1 was.
5. `is_eligible()` is true only while the newest record's version equals the newest sealed
   version. Otherwise it is false and `is_stale()` is true.
6. Records are per case and per version. Assessing again under a newer version writes a new
   record, so a vendor can be re-evaluated without losing what was decided before.

## What the contract stores

| Group | What it is |
| --- | --- |
| policy | node mode (`AND` / `OR` / `ITEM`), parent, leaf label, optional literal keyword, and the version that created the node |
| versions | canonical sealed tree per version, plus the version being edited and whether it is open |
| cases | evidence text, keyed by case id, write once |
| records | per case per version: verdict, demonstrated leaves, cheapest repair, counts |
| counters | node, leaf, case and assessment counts |

## The consumer surface

    is_eligible(case_id)          # bool -- the only one a downstream contract needs
    is_stale(case_id)             # bool -- true when the policy has moved past this record
    verdict_of(case_id)           # str  -- verdict of the newest record
    verdict_at(case_id, version)  # str  -- verdict of one specific version
    history_of(case_id)           # str  -- "v1:ELIGIBLE|v2:MISSING"
    missing_of(case_id)           # str  -- the cheapest set of leaves still needed
    met_of(case_id)               # str  -- leaves the evidence demonstrated
    counts_of(case_id)            # str  -- "<demonstrated>,<still needed>"
    policy_version_of(case_id)    # u256 -- the version the newest record is bound to
    tree_of(version)              # str  -- the canonical sealed tree of a version
    tree()                        # str  -- the tree a new assessment would use
    text_of(case_id)              # str  -- the evidence as registered

A procurement contract, a marketplace intake check or an access broker only needs the
first one, and it fails closed. The rest exist so a human can see what to send next and
which policy decided it.

## Quickstart

    python3 -m venv .venv && . .venv/bin/activate
    pip install -r requirements-dev.txt
    python scripts/prepare_test_sdk.py        # fetches the GenVM binary used by direct mode
    pytest tests/direct -q                     # 55 passed
    genvm-lint check contracts/proof_tree.py   # 3 checks, 32 methods
    genvm-lint typecheck contracts/proof_tree.py

Direct mode runs the real GenVM in memory: no network, no validator set, no keys.

To read the live contract without a wallet, the repo ships its own reader:

    python scripts/read_state.py 0x6f7dd17543b165847c301Dc21DAed004caFd2F9b verdict_of vendor-a
    python scripts/read_state.py 0x6f7dd17543b165847c301Dc21DAed004caFd2F9b history_of vendor-a

## A worked example

Tree: `qualified (AND) -> [soc2, enc (OR) -> [aes, hsm], dpa]`, sealed as version 1.

Evidence: SOC 2 report, signed DPA, nothing about encryption.

1. Keyword floor: no leaf carries a keyword that appears, so nothing is committed.
2. Model: reports `soc2` and `dpa`, each with a span of the text that code finds.
3. Evaluation: `soc2` satisfied, `dpa` satisfied, `enc` unsatisfied. Its two branches cost
   one leaf each, so the tie is broken by the smaller code: `aes`.
4. Verdict `MISSING`, `missing_of` is `aes`, `counts_of` is `2,1`.

Add the sentence "data at rest is protected with AES-256" and the same tree becomes
`ELIGIBLE` without any model call for that leaf, because its keyword is in the text.

Now seal version 2 with one more required leaf. The old verdict stays readable, `is_stale`
turns true, `is_eligible` turns false, and assessing again produces a second record naming
the new gap.

## Bounded shapes

The contract refuses to build a policy it could not read: `add_item` reverts with
`TOO_MANY_LEAVES` on the 41st leaf of a version, so the leaf vocabulary is at most 40. An
answer longer than 80 items is treated as `UNUSABLE` rather than trimmed, so no leaf is
ever silently dropped.

## Where the model can and cannot move the outcome

| The model does this | Result |
| --- | --- |
| reports a registered leaf with a quote that is in the text | the leaf joins the demonstrated set |
| reports a leaf whose quote is not in the text | whole reading `UNUSABLE` |
| reports a code outside the vocabulary | whole reading `UNUSABLE` |
| reports a quote shorter than three words | whole reading `UNUSABLE` |
| returns prose, or no `met` key | whole reading `UNUSABLE` |
| returns more than 80 items | whole reading `UNUSABLE` |
| reports nothing | the keyword floor still decides |

A model cannot invent a leaf, cannot see the declaration or the tree, and cannot choose a
branch. It can only add or omit leaves, and every omission is visible afterwards in
`missing_of`.

## Documentation

- [`docs/DESIGN.md`](docs/DESIGN.md) - state layout, versioning, registration invariants,
  evaluation, threat model and limits.
- [`docs/CONSENSUS.md`](docs/CONSENSUS.md) - the non-deterministic block, the compared
  value, the table of what reaches state, and the forged-leader cases.
- [`EVIDENCE.md`](EVIDENCE.md) - deployment address, every transaction, consensus votes,
  the state reads before and after the policy version changed, and how to reproduce them.

## Licence

MIT.
