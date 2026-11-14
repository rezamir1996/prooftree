# Evidence

Everything below was read back from the chain or from the public repo. No number here is
copied from a screenshot, and every read can be repeated with the script in this repo.

## 1. The deployed contract

Network: GenLayer Studio (studionet).

    contract address   0x0dea3958DB92ce7E7AdE6c36d072763FefBEC856
    owner / deployer   0x74b60694EfBBCF6B5F78240Ed61139282b4C17A9
    constructor arg    vendor-tree-v1
    deploy tx          0xb55e1a96e7ba5d75d66fabc5d5156771c33ebd14b98792149f4f8db8e132646d
    output             FINALIZED

Explorer page:
https://explorer-studio.genlayer.com/address/0x0dea3958DB92ce7E7AdE6c36d072763FefBEC856

### The deployed code is the repo code

The explorer API exposes the executed source for the deploy transaction
(`data.contract_code`, base64). Decoded, it is 20,878 bytes with CRLF line endings.
Converting the line endings to LF and appending one newline gives a byte-identical copy of
`contracts/proof_tree.py`:

    deployed, raw                     20878 bytes, sha256 ec4d340203e034e57a45bab87466db1fa1f49cf7814bdbcb7ba1323199cf96bd
    deployed, LF-normalized           533 lines, sha256 2a4a3c38bab94d118435d2ce5d24cdb73b713abb2156db34e6f45cac725220f3
    contracts/proof_tree.py           534 lines, sha256 b2c0a6348478afecdf4f87dfc9fe72a9c18ac967a8b6accd8e54c68bbdccde4b
    equality test                     deployed_lf + b"\n" == repo file  ->  True

The only difference between the raw bytes is the line ending and the single trailing
newline that the deploy editor strips. There is no hidden code on chain and no local-only
code.

## 2. Every transaction

Eleven transactions, all FINALIZED. The contract is `0x0dea...C856`.

    deploy            0xb55e1a96e7ba5d75d66fabc5d5156771c33ebd14b98792149f4f8db8e132646d  vendor-tree-v1
    add_group         0x4158f650778fac6afbd5e52a35974a158671a0839fcf865cdfa3e8cd0abd4bc2  qualified  ""   AND
    add_item          0x9ce4ff34008fafd8adb6f8e3cb658aa6f9ce60a90b2c629372ec58fe5a69fa43  soc2   qualified  "a SOC 2 Type II report"
    add_group         0x7426fd5b1deedb6c9129d91586a2040729ed70163fc9f9a435361c197be26c31  enc        qualified  OR
    add_item          0xf455201453c8de23040cc9c597371fe0e7e741384a41ca3878ad0fe56431a306  aes    enc  "encryption at rest with AES-256"  keyword aes-256
    add_item          0xbb4ee6f22f204cd5fb0b88c47d29f13a9dfb12670c7dede8017b4f61af1afa91  hsm    enc  "keys held in an HSM or managed KMS"
    add_item          0x5324b0e0874d05096a3521390ffcefe05b26c2ce14b52ac8af5917abffbee7d0  dpa    qualified  "a signed data processing agreement"
    register_case     0xd71aff51ca549453cedb84a6ef8aa1333f67f85cdade754da7dc838be6c029db  vendor-a
    assess            0x4c8fd6a9419112866fa5134b64d93ddb6f8b6309345298644610a955d596efc5  vendor-a  -> ELIGIBLE
    register_case     0xbf1b28f1cc5f9f595a43b9baaeee375300aee0712501437de00725040d86e133  vendor-b
    assess            0xa57a86cba65ab4b044eb4a3c42d7d38db2b69586c1316773c0b5f637dac6dde5  vendor-b  -> MISSING

Every hash was resolved through the explorer API and its calldata decoded, so the method
name and every argument listed are the ones that actually executed.

## 3. Consensus

Both assessments ran `execution_mode = NORMAL` with five initial validators,
`leader_only = false` and `rotation_count = 0`: no node disagreed, so no rotation was
needed. Three validators voted `agree` and two did not vote, on both.

    assess vendor-a   leader + validators returned   ELIGIBLE   agree 3, idle 2, disagree 0
    assess vendor-b   leader + validators returned   MISSING    agree 3, idle 2, disagree 0

This is the point of the design. The non-deterministic block returns exactly one string,
`OK:<sorted leaf codes>` or `UNUSABLE`, and the validator compares only that string against
its own independent reading. The leader's quotes, its reasoning and its per-item confidence
never travel, so nothing outside the compared value can decide a stored verdict. A
validator that cannot parse the leader's payload returns disagree without inspecting
anything else.

## 4. On-chain state, read back

Read with `gen_call` (`type: "read"`, `transaction_hash_variant: latest-nonfinal`) against
`https://studio.genlayer.com/api`. Read-only: no wallet, no signature, no transaction.

    config                     vendor-tree-v1|6|4      (site label, nodes, leaves)
    root_of                    qualified
    node_count                 6
    leaf_count                 4
    case_count                 2

    verdict_of(vendor-a)       ELIGIBLE
    met_of(vendor-a)           aes,dpa,soc2
    missing_of(vendor-a)       (empty)
    counts_of(vendor-a)        3,0
    is_eligible(vendor-a)      True

    verdict_of(vendor-b)       MISSING
    met_of(vendor-b)           soc2
    missing_of(vendor-b)       aes,dpa
    counts_of(vendor-b)        1,2
    is_eligible(vendor-b)      False

    is_eligible(vendor-zzz)    False     (never registered: the gate fails closed)

`counts_of` is `<demonstrated>,<still needed>`.

## 5. Why these two cases

The pair is chosen so that the same contract produces both outcomes and so that each layer
does visible work.

vendor-a.

    tree        qualified (AND) -> soc2, enc (OR) -> aes, hsm, dpa
    evidence    SOC 2 report, AES-256 at rest, signed DPA
    aes         committed by the literal keyword "aes-256" in the folded text,
                with no model involvement at all
    soc2, dpa   reported by the model, each with a span that code found in the text
    derivation  every leaf satisfied, enc satisfied by its aes branch -> ELIGIBLE

vendor-b.

    evidence    SOC 2 report only, encryption "available on request"
    soc2        reported by the model
    enc         unsatisfied; both branches cost one leaf, so the smaller code wins
    derivation  missing = aes, dpa -> MISSING, counts 1,2

Two things are being demonstrated. First, the answer is a repair plan, not a complaint:
`missing_of` names `aes` alone, not `aes,hsm`, because either branch of the OR would do.
Second, the gate answers per leaf rather than per document: the same tree passes evidence
that says "AES-256" and fails evidence that says "encryption available on request", with
nothing in between that a human would have to interpret.

The tree shape is public. Any builder can recompute every number above from
`node_mode_of`, `node_parent_of` and the two leaf sets without trusting this file.

## 6. Tests

    source         contracts/proof_tree.py           20,346 bytes, 534 lines, 20 methods
    tests          tests/direct/test_proof_tree.py   15,507 bytes, 427 lines
    result         pytest tests/direct -q            -> 38 passed
    linter         genvm-lint check                  -> passed, 3 checks, 20 methods
    typecheck      genvm-lint typecheck              -> no type errors

The direct-mode suite covers the keyword floor and its token alignment, the model layer,
the merge of the two, every unusable-reading path, the AND union, the OR cheapest-branch
rule including the tie-break, a nested tree, a single-leaf root, re-assessment refusal, an
unknown case, the fail-closed gate, every registration invariant (owner only, single root,
unknown parent, leaf as parent, empty group, invalid mode), and the six forged-leader
cases in `docs/CONSENSUS.md`.

## 7. Reproducing these reads

    pip install -r requirements-dev.txt
    python scripts/prepare_test_sdk.py
    pytest tests/direct -q

    python scripts/read_state.py 0x0dea3958DB92ce7E7AdE6c36d072763FefBEC856 config
    python scripts/read_state.py 0x0dea3958DB92ce7E7AdE6c36d072763FefBEC856 verdict_of vendor-b
    python scripts/read_state.py 0x0dea3958DB92ce7E7AdE6c36d072763FefBEC856 missing_of vendor-b

`scripts/read_state.py` carries its own calldata codec and the RLP framing the RPC expects,
so it needs nothing but Python and curl.

## 8. Repo

https://github.com/rezamir1996/prooftree

    contracts/proof_tree.py           the contract
    tests/direct/test_proof_tree.py   the direct-mode suite
    scripts/prepare_test_sdk.py       fetches the GenVM build that direct-mode tests load
    scripts/read_state.py             reads this contract from the public RPC, no wallet
    docs/DESIGN.md                    state, invariants, evaluation, threat model, limits
    docs/CONSENSUS.md                 the compared value and what is outside consensus
    gltest.config.yaml                network and test paths
    requirements-dev.txt              pinned test dependencies
