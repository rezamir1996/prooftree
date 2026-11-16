# Evidence

Everything below was read back from the chain or from the public repo. No number here is
copied from a screenshot, and every read can be repeated with the script in this repo.

This deployment replaces the earlier `vendor-tree-v1` deployment. That one had two real
defects, described in section 6, and is not presented as correct.

## 1. The deployed contract

Network: GenLayer Studio (studionet).

    contract address   0x6f7dd17543b165847c301Dc21DAed004caFd2F9b
    owner / deployer   0x74b60694EfBBCF6B5F78240Ed61139282b4C17A9
    constructor arg    vendor-tree-v2
    deploy tx          0xffedbe3ed25686d0906b2f54b2ce3a6e5d739a73910eeb3218835e798eee250f
    output             FINALIZED

Explorer page:
https://explorer-studio.genlayer.com/address/0x6f7dd17543b165847c301Dc21DAed004caFd2F9b

### The deployed code is the repo code

The explorer API exposes the source that actually executed for the deploy transaction
(`data.contract_code`, base64). Decoded it is 30,589 bytes with CRLF line endings.
Normalising the line endings to LF gives 29,832 bytes and 757 newlines, and the repo file
`contracts/proof_tree.py` is 29,833 bytes and 758 newlines. The only difference between
them is the single trailing newline that the deploy editor strips:

    deployed, raw                 30589 bytes  sha256 a1f552af4431352cda3414b53d94549488d6854c78f32d43b414f5aa457b4122
    deployed, LF-normalised       29832 bytes  sha256 1974b67717537a0a108e3339e75775537a915c46d72ce21952b679d04a90a97c
    contracts/proof_tree.py       29833 bytes  sha256 f849a291685c0e83afc66daa01a71bfb03414f006faf88395d450e14586f594d

    equality test                 deployed_lf == repo.rstrip(b"\n")  ->  True

The repository side was checked the same way, from the GitHub contents API rather than a
raw URL, so what is compared is the blob the repo actually serves:

    contracts/proof_tree.py             sha256 f849a291685c0e83afc66daa01a71bfb03414f006faf88395d450e14586f594d
    tests/direct/test_proof_tree.py     sha256 6ec7a87feb69b124926541c7fd35ddd0c0a0727100a290d5c4f1cc008f23757b

Those two hashes are the same as the local files that produced the test run in section 7.
There is no hidden code on chain and no local-only code.

## 2. Every transaction

Sixteen transactions, all FINALIZED, all against `0x6f7d...2F9b`. Every hash below was
resolved through the explorer API and its calldata decoded, so the method name and the
arguments listed are the ones that executed.

    deploy            0xffedbe3ed25686d0906b2f54b2ce3a6e5d739a73910eeb3218835e798eee250f  vendor-tree-v2
    add_group         0xde30947981d8aaacd315dc97806d90e1de56dc4bb13ab74f2187d0ffbac9649f  qualified  ""   AND
    add_item          0x2610b23616251c33df98dda4ecf627e0eb0d053945500fff71a17bd520133185  soc2   qualified  "a SOC 2 Type II report"
    add_group         0x0af54e17f1f1a7b59fcc40358ab7d688b90d7d87f2de404bfdde4338fc5e4ef6  enc        qualified  OR
    add_item          0x0a5bbf1c68b6d3033da5015be9804b34e71e872d4501c0b6261cc19ad1e513b2  aes    enc  "encryption at rest with AES-256"  keyword "aes-256"
    add_item          0xfe4b5e1176804d752512327f3f566b690f065302f562de2b00aba0471960b2d9  hsm    enc  "keys held in an HSM or managed KMS"
    add_item          0xfcf98d2443d14039a7d8479b9daaca5aec444d7049daaa6ab135be39fe46a177  dpa    qualified  "a signed data processing agreement"
    seal_policy       0xcac2c9038ce387ca194dcbc2f97e84675ff9b3daf1449b420dd2f83d3daa59fc  -> version 1 sealed
    register_case     0x6ca8ed464aad0d19217862895861c37ec3a931177db97fbb76cd588add0df12a  vendor-a
    assess            0x47bbbcd9d045b5a5ba66c40357edeec745d052a429d4e17dd0d4ff087c29804b  vendor-a  -> ELIGIBLE
    register_case     0xdc06c9e75e41263a3b38bcae5552511047dc00e667b427dead2fcb35ccd1971d  vendor-b
    assess            0x2e55ee40e881095c8cffda1bdf2159a9d165ae1b31668f8a9b2c4444c792837b  vendor-b  -> MISSING
    open_policy       0x5ea26f5c0413a5dda663474a38facc0d1790afb6edaa00e34d0a3047afa629e7  -> version 2 open
    add_item          0x4e8baa0b6f6f833421b121d37974272337b93f3cd52385133cfe066cbbcd23b4  pentest  qualified  "an annual penetration test by an independent auditor"
    seal_policy       0xda088714d4719b3f5f430cf345fade6e65f91c7abb7cc1a8231d0cec1b46d047  -> version 2 sealed
    assess            0x2de3026e4f38d62ae4baabbe92fadb0afe395bfa82cdfdbb923ebaee7f806ca1  vendor-a under v2  -> MISSING

## 3. Consensus

The three assessments each ran a fresh non-deterministic block with five initial
validators, `leader_only = false` and `rotation_count = 0`: no node disagreed, so no
rotation was needed.

    assess vendor-a            ELIGIBLE   agree 3, idle 2, disagree 0
    assess vendor-b            MISSING    agree 3, idle 2, disagree 0
    assess vendor-a under v2   MISSING    agree 3, idle 1, disagree 0

This is the point of the design. The non-deterministic block returns exactly one string,
`OK:<sorted leaf codes>` or `UNUSABLE`, and the validator compares only that string against
its own independent reading. The leader's quotes, its reasoning and its per-item confidence
never travel, so nothing outside the compared value can decide a stored verdict.

## 4. The sealed policy, version by version

The canonical form is sorted by node code, so it does not depend on the order of the
writes. Read back with `tree_of(1)` and `tree_of(2)`:

    v1  aes:ITEM:enc|dpa:ITEM:qualified|enc:OR:qualified|hsm:ITEM:enc|qualified:AND:|soc2:ITEM:qualified

    v2  aes:ITEM:enc|dpa:ITEM:qualified|enc:OR:qualified|hsm:ITEM:enc|pentest:ITEM:qualified|qualified:AND:|soc2:ITEM:qualified

Version 1 is what both vendors were assessed against, and it is still on chain, byte for
byte as it was published. Version 2 adds one leaf, `pentest`, under `qualified`.

    config       'vendor-tree-v2|7|5|v2|sealed'      (site | nodes | leaves | version | state)
    leaf_count   5        node_version_of(pentest) = 2        node_version_of(soc2) = 1

## 5. On-chain state, read back

Every value below came from `gen_call` against the public RPC through
`scripts/read_state.py`. No wallet was used and nothing was trusted from the UI.

### After version 1 was sealed and both vendors assessed

    verdict_of vendor-a          ELIGIBLE      met aes,dpa,soc2      missing ""       counts 3,0
    is_eligible vendor-a         True          is_stale False        policy_version_of 1
    history_of vendor-a          v1:ELIGIBLE

    verdict_of vendor-b          MISSING       met dpa,soc2          missing aes      counts 2,1
    is_eligible vendor-b         False         is_stale False        policy_version_of 1

    case_count 2       assessment_count 2       current_version 1

`aes` in the first row was not found by the model: the leaf carries the literal keyword
`aes-256`, so the deterministic floor committed it before any model call. `missing` in the
second row reports `aes` and not `aes,hsm`, because the OR node names the cheaper of its
two branches.

### After version 2 was sealed, before any new assessment

    current_version              2
    is_open                      False
    config                       'vendor-tree-v2|7|5|v2|sealed'
    tree_of 1                    unchanged, still the v1 string above
    tree_of 2                    the v2 string above
    verdict_of vendor-a          ELIGIBLE       <- the stored record did not change
    policy_version_of vendor-a   1              <- it is bound to version 1
    verdict_at vendor-a 1        ELIGIBLE
    is_stale vendor-a            True
    is_eligible vendor-a         False          <- the gate failed closed
    history_of vendor-a          v1:ELIGIBLE

This is the correction the steward asked for, on chain. The policy moved; the old verdict
is still readable and still says what was decided and under which tree; and the boolean a
consumer reads no longer reports it.

### After assessing vendor-a again, under version 2

    verdict_of vendor-a          MISSING       met aes,dpa,soc2   missing pentest   counts 3,1
    policy_version_of vendor-a   2             is_stale False     is_eligible False
    history_of vendor-a          v1:ELIGIBLE|v2:MISSING
    verdict_at vendor-a 1        ELIGIBLE      verdict_at vendor-a 2  MISSING
    case_count 2                 assessment_count 3

Neither record overwrote the other. The evidence never changed; the published policy did,
and the contract says so in one string.

## 6. The two corrections, and what closes each

### (a) A verdict could outlive the policy it was decided under

The old deployment let the owner add a leaf after an assessment while `is_eligible` kept
returning the earlier `ELIGIBLE`. In this version:

- `assess()` refuses to run unless the current version is sealed (`POLICY_NOT_SEALED`).
- `seal_policy()` stores the canonical tree of the version and closes it; afterwards
  `add_group` and `add_item` revert with `POLICY_SEALED`.
- `open_policy()` starts a new version. Sealed versions are never edited, because nodes
  carry the version that created them and are read through it (`_in_version`).
- Every assessment is stored as a record keyed by case and version, and
  `is_eligible()` is true only while the newest record's version equals the newest sealed
  version. Otherwise it returns false and `is_stale()` returns true.

On chain: section 5, second table. In the suite:

    test_a_new_version_marks_earlier_verdicts_stale
    test_policy_edits_are_refused_after_sealing
    test_assessment_requires_a_sealed_policy
    test_a_policy_cannot_be_sealed_twice
    test_opening_a_policy_requires_a_seal
    test_an_open_draft_does_not_change_the_effective_policy
    test_a_new_version_is_evaluated_with_the_leaves_it_contains
    test_an_older_assessment_can_be_refreshed_under_a_new_version
    test_gate_fails_closed_for_an_unknown_case

### (b) The 40-leaf limit was only enforced while reading

The old deployment enforced `MAX_LEAVES = 40` inside the reading step only, so a policy
with more leaves could be registered and the model's answer was trimmed to 40. In this
version the bound is enforced where the policy is built and an over-long answer is refused
rather than cut:

- `add_item()` reverts with `TOO_MANY_LEAVES` when the open version already holds 40
  leaves, so a policy the reading step could not cover cannot exist.
- `_judge()` treats an answer with more than `MAX_REPORTED = 80` items as `UNUSABLE`. It is
  never truncated, so no leaf is silently dropped.
- `MAX_NODES = 64` still bounds the tree, and `MAX_LEAVES = 40` is derivable from it.

In the suite:

    test_the_forty_first_leaf_is_refused            (40 added, the 41st reverts TOO_MANY_LEAVES)
    test_a_forty_leaf_policy_can_be_sealed_and_read (40 leaves seal and evaluate with 39 missing)
    test_an_answer_at_the_report_bound_is_still_a_reading   (80 items -> a reading)
    test_an_oversized_answer_is_unusable_rather_than_truncated  (81 items -> UNUSABLE)

## 7. The test run these numbers come from

    $ pytest tests/direct -q
    55 passed

    $ genvm-lint check contracts/proof_tree.py
    Lint passed (3 checks), Validation passed, Methods: 32 (26 view, 6 write)

    $ genvm-lint typecheck contracts/proof_tree.py
    No type errors found

Direct mode runs the real GenVM in memory: no network, no validator set, no keys. The
fixtures in the suite are the same texts that were registered on chain, and the on-chain
readings above match the assertions in the suite line for line.

## 8. Reproducing the reads

    python3 scripts/read_state.py 0x6f7dd17543b165847c301Dc21DAed004caFd2F9b config
    python3 scripts/read_state.py 0x6f7dd17543b165847c301Dc21DAed004caFd2F9b tree_of 1
    python3 scripts/read_state.py 0x6f7dd17543b165847c301Dc21DAed004caFd2F9b verdict_of vendor-a
    python3 scripts/read_state.py 0x6f7dd17543b165847c301Dc21DAed004caFd2F9b is_eligible vendor-a
    python3 scripts/read_state.py 0x6f7dd17543b165847c301Dc21DAed004caFd2F9b is_stale vendor-a
    python3 scripts/read_state.py 0x6f7dd17543b165847c301Dc21DAed004caFd2F9b history_of vendor-a

The script is standard library only: it builds the GenLayer calldata, posts `gen_call` to
the public Studio RPC and prints the decoded return value.
