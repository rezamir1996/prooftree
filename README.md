# ProofTree

An on-chain eligibility gate for evidence that arrives as prose. A published AND/OR
requirement tree, a model that may only name leaves it can quote, and code that decides.

    evidence text  ->  [ model names leaves, code checks the quotes ]  ->  leaf set
    leaf set + published tree  ->  AND/OR evaluation  ->  ELIGIBLE or the cheapest repair

If the tree is satisfied the verdict is `ELIGIBLE`. If it is not, the contract does not
just say "no": it returns the smallest set of leaves that would make it yes. If the reading
cannot be trusted the verdict is `UNUSABLE` and the gate returns `false`.

## Live on Studio

    contract       0x0dea3958DB92ce7E7AdE6c36d072763FefBEC856
    explorer       https://explorer-studio.genlayer.com/address/0x0dea3958DB92ce7E7AdE6c36d072763FefBEC856
    deploy tx      0xb55e1a96e7ba5d75d66fabc5d5156771c33ebd14b98792149f4f8db8e132646d
    site_label     vendor-tree-v1

The published tree used in the live run:

    qualified (AND)
      +-- soc2        a SOC 2 Type II report
      +-- enc (OR)
      |     +-- aes        encryption at rest with AES-256
      |     +-- hsm        keys held in an HSM or managed KMS
      +-- dpa         a signed data processing agreement

Two cases are registered and assessed. Both branches of the decision are live:

| case | evidence shows | verdict | demonstrated | missing | counts |
| --- | --- | --- | --- | --- | --- |
| `vendor-a` | SOC 2 report, AES-256, signed DPA | `ELIGIBLE` | `aes,dpa,soc2` | - | `3,0` |
| `vendor-b` | SOC 2 report only | `MISSING` | `soc2` | `aes,dpa` | `1,2` |

`counts_of` is `<demonstrated>,<still needed>`, and `is_eligible` was read back as `true`
for `vendor-a`, `false` for `vendor-b`, and `false` for a case id that was never
registered.

Two things to notice in the second row. `missing` reports `aes`, not `aes,hsm`: the OR
node is unsatisfied, and the contract names the cheaper of its two branches rather than
everything that fails. And `aes` in the first row was not found by the model at all - the
leaf carries the literal keyword `aes-256`, so the deterministic floor committed it.

Addresses, all eleven transaction hashes and the validator votes are in
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
owner, and turning an AND into an OR is an on-chain write that anyone can read.

## What the contract stores

| Group | What it is |
| --- | --- |
| policy | node mode (`AND` / `OR` / `ITEM`), parent, leaf label, optional literal keyword |
| cases | evidence text, keyed by case id, write once |
| verdict | `ELIGIBLE` / `MISSING` / `UNUSABLE`, the demonstrated leaves, the cheapest repair, the counts |
| counters | node, leaf and case counts |

`assess()` is write-once per case: the first verdict stands, so the record is a statement
about one piece of evidence at one time rather than a value anyone can refresh.

## The consumer surface

    is_eligible(case_id)    # bool -- fails closed: false when missing, unusable or unknown
    verdict_of(case_id)     # str  -- ELIGIBLE | MISSING | UNUSABLE | "" before assessment
    missing_of(case_id)     # str  -- the cheapest set of leaves still needed
    met_of(case_id)         # str  -- leaves the evidence demonstrated
    counts_of(case_id)      # str  -- "<demonstrated>,<still needed>"
    text_of(case_id)        # str  -- the evidence as registered

A procurement contract, a marketplace intake check or an access broker only needs the
first one. The rest exist so a human can see what to send next.

## Quickstart

    python3 -m venv .venv && . .venv/bin/activate
    pip install -r requirements-dev.txt
    python scripts/prepare_test_sdk.py        # fetches the GenVM binary used by direct mode
    pytest tests/direct -q                     # 38 passed
    genvm-lint check contracts/proof_tree.py   # 3 checks, 20 methods
    genvm-lint typecheck contracts/proof_tree.py

Direct mode runs the real GenVM in memory: no network, no validator set, no keys.

To read the live contract without a wallet, the repo ships its own reader:

    python scripts/read_state.py 0x0dea3958DB92ce7E7AdE6c36d072763FefBEC856 verdict_of vendor-a
    python scripts/read_state.py 0x0dea3958DB92ce7E7AdE6c36d072763FefBEC856 missing_of vendor-b

## A worked example

Tree: `root (AND) -> [soc2, enc (OR) -> [aes, hsm], dpa]`.

Evidence: SOC 2 report, signed DPA, nothing about encryption.

1. Keyword floor: no leaf carries a keyword that appears, so nothing is committed.
2. Model: reports `soc2` and `dpa`, each with a span of the text that code finds.
3. Evaluation: `soc2` satisfied, `dpa` satisfied, `enc` unsatisfied. Its two branches cost
   one leaf each, so the tie is broken by the smaller code: `aes`.
4. Verdict `MISSING`, `missing_of` is `aes`, `counts_of` is `2,1`.

Add the sentence "data at rest is protected with AES-256" and the same tree becomes
`ELIGIBLE` without any model call for that leaf, because its keyword is in the text.

## Where the model can and cannot move the outcome

| The model does this | Result |
| --- | --- |
| reports a registered leaf with a quote that is in the text | the leaf joins the demonstrated set |
| reports a leaf whose quote is not in the text | whole reading `UNUSABLE` |
| reports a code outside the vocabulary | whole reading `UNUSABLE` |
| reports a quote shorter than three words | whole reading `UNUSABLE` |
| returns prose, or no `met` key | whole reading `UNUSABLE` |
| reports nothing | the keyword floor still decides |

A model cannot invent a leaf, cannot see the declaration or the tree, and cannot choose a
branch. It can only add or omit leaves, and every omission is visible afterwards in
`missing_of`.

## Documentation

- [`docs/DESIGN.md`](docs/DESIGN.md) - state layout, registration invariants, evaluation,
  threat model and limits.
- [`docs/CONSENSUS.md`](docs/CONSENSUS.md) - the non-deterministic block, the compared
  value, the table of what reaches state, and the forged-leader cases.
- [`EVIDENCE.md`](EVIDENCE.md) - deployment address, every transaction, consensus votes,
  and how to reproduce the reads.

## Licence

MIT.
