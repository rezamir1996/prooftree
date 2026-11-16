"""Direct-mode tests for ProofTree. No network, no Studio: the GenVM runs in memory.

ASCII only.
"""

FULL = (
    "Our controls are audited annually. A SOC 2 Type II report covering the production "
    "environment is available. Data at rest is protected with AES-256. A signed data "
    "processing agreement is in place for every customer."
)

PARTIAL = (
    "Our controls are audited annually. A SOC 2 Type II report covering the production "
    "environment is available. Data at rest is protected with an internal cipher suite."
)

MIDDLE = (
    "Our controls are audited annually. A SOC 2 Type II report covering the production "
    "environment is available. A signed data processing agreement is in place for every "
    "customer."
)

PROMPT = r"(?s).*which of the listed requirements.*"


def _proof(direct_deploy, name="vendor-policy"):
    return direct_deploy("contracts/proof_tree.py", name)


def _policy(proof):
    """root AND -> soc2, enc OR(aes, hsm), dpa. Sealed as version 1."""
    proof.add_group("qualified", "", "AND")
    proof.add_item("soc2", "qualified", "a SOC 2 Type II report", "")
    proof.add_group("enc", "qualified", "OR")
    proof.add_item("aes", "enc", "encryption at rest with AES-256", "aes-256")
    proof.add_item("hsm", "enc", "keys held in an HSM or managed KMS", "")
    proof.add_item("dpa", "qualified", "a signed data processing agreement", "")
    proof.seal_policy()
    return proof


def _say(*pairs):
    """Build a model answer from (code, quote) pairs."""
    parts = []
    for code, quote in pairs:
        parts.append('{"code": "' + code + '", "quote": "' + quote + '"}')
    return '{"met": [' + ", ".join(parts) + "]}"


def _none(direct_vm):
    direct_vm.mock_llm(PROMPT, '{"met": []}')


SOC2_Q = "a soc 2 type ii report covering the production environment"
DPA_Q = "a signed data processing agreement is in place"


# ------------------------------------------------------------ deterministic layer
def test_keyword_commits_a_leaf_without_a_model(direct_vm, direct_deploy):
    """The AES leaf carries the literal keyword, so no model answer is needed for it."""
    proof = _policy(_proof(direct_deploy))
    proof.register_case("c1", FULL)
    direct_vm.mock_llm(PROMPT, _say(("soc2", SOC2_Q), ("dpa", DPA_Q)))

    assert proof.assess("c1") == "ELIGIBLE"
    assert proof.met_of("c1") == "aes,dpa,soc2"
    assert proof.missing_of("c1") == ""
    assert proof.counts_of("c1") == "3,0"
    assert proof.is_eligible("c1") is True
    assert proof.is_stale("c1") is False
    assert proof.policy_version_of("c1") == 1


def test_keyword_match_is_token_aligned(direct_vm, direct_deploy):
    """A keyword must not fire inside a longer word."""
    proof = _proof(direct_deploy)
    proof.add_group("root", "", "AND")
    proof.add_item("soc", "root", "a SOC 2 report", "soc")
    proof.seal_policy()
    proof.register_case("c2", "We are a socially responsible employer with an audit.")

    _none(direct_vm)
    assert proof.assess("c2") == "MISSING"
    assert proof.missing_of("c2") == "soc"


def test_single_missing_leaf_is_named(direct_vm, direct_deploy):
    proof = _policy(_proof(direct_deploy))
    proof.register_case("c3", PARTIAL)
    direct_vm.mock_llm(PROMPT, _say(("soc2", SOC2_Q)))

    assert proof.assess("c3") == "MISSING"
    assert proof.missing_of("c3") == "aes,dpa"
    assert proof.counts_of("c3") == "1,2"
    assert proof.is_eligible("c3") is False


def test_or_group_is_satisfied_by_either_branch(direct_vm, direct_deploy):
    proof = _policy(_proof(direct_deploy))
    proof.register_case("c4", FULL)
    direct_vm.mock_llm(PROMPT, _say(("soc2", SOC2_Q), ("dpa", DPA_Q)))

    assert proof.assess("c4") == "ELIGIBLE"
    assert proof.met_of("c4") == "aes,dpa,soc2"


def test_unsatisfied_or_reports_the_cheapest_branch(direct_vm, direct_deploy):
    """enc has two one-leaf branches; the lexicographically smaller code is reported."""
    proof = _policy(_proof(direct_deploy))
    proof.register_case("c5", MIDDLE)
    direct_vm.mock_llm(PROMPT, _say(("soc2", SOC2_Q), ("dpa", DPA_Q)))

    assert proof.assess("c5") == "MISSING"
    assert proof.missing_of("c5") == "aes"
    assert proof.counts_of("c5") == "2,1"


def test_unsatisfied_or_prefers_the_branch_that_needs_less(direct_vm, direct_deploy):
    """A two-leaf AND branch loses against a one-leaf branch, whatever the codes are."""
    proof = _proof(direct_deploy)
    proof.add_group("root", "", "AND")
    proof.add_group("gate", "root", "OR")
    proof.add_group("aaa", "gate", "AND")
    proof.add_item("a1", "aaa", "first hard control", "")
    proof.add_item("a2", "aaa", "second hard control", "")
    proof.add_item("zzz", "gate", "one cheap control", "")
    proof.add_item("memo", "root", "a written memo", "")
    proof.seal_policy()
    proof.register_case("c6", "Nothing relevant is described in this evidence at all.")

    _none(direct_vm)
    assert proof.assess("c6") == "MISSING"
    assert proof.missing_of("c6") == "memo,zzz"
    assert proof.counts_of("c6") == "0,2"


def test_nested_and_groups_add_up(direct_vm, direct_deploy):
    proof = _proof(direct_deploy)
    proof.add_group("root", "", "AND")
    proof.add_group("g1", "root", "AND")
    proof.add_item("i1", "g1", "first control", "")
    proof.add_item("i2", "g1", "second control", "")
    proof.add_item("i3", "root", "third control", "")
    proof.seal_policy()
    proof.register_case("c7", "This evidence mentions the first control only.")
    direct_vm.mock_llm(PROMPT, _say(("i1", "this evidence mentions the first control")))

    assert proof.assess("c7") == "MISSING"
    assert proof.met_of("c7") == "i1"
    assert proof.missing_of("c7") == "i2,i3"
    assert proof.counts_of("c7") == "1,2"


def test_a_tree_whose_root_is_one_leaf(direct_vm, direct_deploy):
    proof = _proof(direct_deploy)
    proof.add_item("only", "", "the only requirement", "only requirement")
    proof.seal_policy()
    proof.register_case("c8", "We satisfy the only requirement set out in the policy.")

    _none(direct_vm)
    assert proof.assess("c8") == "ELIGIBLE"
    assert proof.root_of() == "only"
    assert proof.is_eligible("c8") is True


# ------------------------------------------------------------- unusable readings
def test_quote_that_is_not_in_the_evidence_makes_the_reading_unusable(
    direct_vm, direct_deploy
):
    proof = _policy(_proof(direct_deploy))
    proof.register_case("c9", PARTIAL)
    direct_vm.mock_llm(PROMPT, _say(("soc2", "we hold an iso 27001 certificate")))

    assert proof.assess("c9") == "UNUSABLE"
    assert proof.met_of("c9") == ""
    assert proof.counts_of("c9") == "0,0"
    assert proof.is_eligible("c9") is False


def test_code_outside_the_vocabulary_makes_the_reading_unusable(
    direct_vm, direct_deploy
):
    proof = _policy(_proof(direct_deploy))
    proof.register_case("c10", PARTIAL)
    direct_vm.mock_llm(PROMPT, _say(("pen-test", SOC2_Q)))

    assert proof.assess("c10") == "UNUSABLE"


def test_quote_shorter_than_three_words_makes_the_reading_unusable(
    direct_vm, direct_deploy
):
    proof = _policy(_proof(direct_deploy))
    proof.register_case("c11", PARTIAL)
    direct_vm.mock_llm(PROMPT, _say(("soc2", "soc 2")))

    assert proof.assess("c11") == "UNUSABLE"


def test_prose_answer_makes_the_reading_unusable(direct_vm, direct_deploy):
    proof = _policy(_proof(direct_deploy))
    proof.register_case("c12", PARTIAL)
    direct_vm.mock_llm(PROMPT, "The vendor looks compliant to me.")

    assert proof.assess("c12") == "UNUSABLE"


def test_an_answered_list_without_a_code_key_is_dropped(direct_vm, direct_deploy):
    proof = _policy(_proof(direct_deploy))
    proof.register_case("c13", PARTIAL)
    direct_vm.mock_llm(PROMPT, '{"met": [{"what": "soc2", "quote": "' + SOC2_Q + '"}]}')

    assert proof.assess("c13") == "UNUSABLE"


def test_a_duplicate_report_of_one_leaf_is_counted_once(direct_vm, direct_deploy):
    proof = _policy(_proof(direct_deploy))
    proof.register_case("c14", FULL)
    direct_vm.mock_llm(
        PROMPT,
        _say(("soc2", SOC2_Q), ("soc2", "controls are audited annually"), ("dpa", DPA_Q)),
    )

    assert proof.assess("c14") == "ELIGIBLE"
    assert proof.met_of("c14") == "aes,dpa,soc2"


def test_an_answer_at_the_report_bound_is_still_a_reading(direct_vm, direct_deploy):
    """80 items is the most the contract will read, duplicates included."""
    proof = _policy(_proof(direct_deploy))
    proof.register_case("c15", PARTIAL)
    one = '{"code": "soc2", "quote": "' + SOC2_Q + '"}'
    direct_vm.mock_llm(PROMPT, '{"met": [' + ",".join([one] * 80) + "]}")

    assert proof.assess("c15") == "MISSING"
    assert proof.met_of("c15") == "soc2"


def test_an_oversized_answer_is_unusable_rather_than_truncated(
    direct_vm, direct_deploy
):
    """81 items is over the bound. The answer is refused, never trimmed to fit."""
    proof = _policy(_proof(direct_deploy))
    proof.register_case("c16", PARTIAL)
    one = '{"code": "soc2", "quote": "' + SOC2_Q + '"}'
    direct_vm.mock_llm(PROMPT, '{"met": [' + ",".join([one] * 81) + "]}")

    assert proof.assess("c16") == "UNUSABLE"
    assert proof.met_of("c16") == ""


# -------------------------------------------------------------------- validator
def test_validator_agrees_when_the_reading_matches(direct_vm, direct_deploy):
    proof = _policy(_proof(direct_deploy))
    proof.register_case("c17", PARTIAL)
    direct_vm.mock_llm(PROMPT, _say(("soc2", SOC2_Q)))
    proof.assess("c17")

    assert direct_vm.run_validator() is True


def test_validator_rejects_an_extra_leaf(direct_vm, direct_deploy):
    proof = _policy(_proof(direct_deploy))
    proof.register_case("c18", PARTIAL)
    direct_vm.mock_llm(PROMPT, _say(("soc2", SOC2_Q)))
    proof.assess("c18")

    forged = {"signal": "OK:dpa,soc2", "codes": ["dpa", "soc2"]}
    assert direct_vm.run_validator(leader_result=forged) is False


def test_validator_rejects_a_missing_leaf(direct_vm, direct_deploy):
    proof = _policy(_proof(direct_deploy))
    proof.register_case("c19", PARTIAL)
    direct_vm.mock_llm(PROMPT, _say(("soc2", SOC2_Q)))
    proof.assess("c19")

    assert direct_vm.run_validator(leader_result={"signal": "OK:"}) is False


def test_validator_rejects_a_usable_reading_reported_as_unusable(
    direct_vm, direct_deploy
):
    proof = _policy(_proof(direct_deploy))
    proof.register_case("c20", PARTIAL)
    direct_vm.mock_llm(PROMPT, _say(("soc2", SOC2_Q)))
    proof.assess("c20")

    assert direct_vm.run_validator(leader_result={"signal": "UNUSABLE"}) is False


def test_validator_rejects_an_unusable_reading_reported_as_usable(
    direct_vm, direct_deploy
):
    proof = _policy(_proof(direct_deploy))
    proof.register_case("c21", PARTIAL)
    direct_vm.mock_llm(PROMPT, _say(("soc2", "an iso certificate we do not have")))
    proof.assess("c21")

    assert direct_vm.run_validator(leader_result={"signal": "OK:"}) is False


def test_validator_rejects_a_payload_without_a_signal(direct_vm, direct_deploy):
    proof = _policy(_proof(direct_deploy))
    proof.register_case("c22", PARTIAL)
    direct_vm.mock_llm(PROMPT, _say(("soc2", SOC2_Q)))
    proof.assess("c22")

    assert direct_vm.run_validator(leader_result={"codes": ["soc2"]}) is False


def test_validator_rejects_a_leader_that_errored(direct_vm, direct_deploy):
    proof = _policy(_proof(direct_deploy))
    proof.register_case("c23", PARTIAL)
    direct_vm.mock_llm(PROMPT, _say(("soc2", SOC2_Q)))
    proof.assess("c23")

    assert direct_vm.run_validator(leader_error=RuntimeError("boom")) is False


# ------------------------------------------------------- policy version binding
def test_assessment_requires_a_sealed_policy(direct_vm, direct_deploy):
    proof = _proof(direct_deploy)
    proof.add_group("root", "", "AND")
    proof.add_item("soc", "root", "a SOC 2 report", "")
    proof.register_case("v1", PARTIAL)
    with direct_vm.expect_revert("POLICY_NOT_SEALED"):
        proof.assess("v1")


def test_policy_edits_are_refused_after_sealing(direct_vm, direct_deploy):
    proof = _policy(_proof(direct_deploy))
    with direct_vm.expect_revert("POLICY_SEALED"):
        proof.add_item("pentest", "qualified", "an annual penetration test", "")
    with direct_vm.expect_revert("POLICY_SEALED"):
        proof.add_group("extra", "qualified", "OR")


def test_a_policy_cannot_be_sealed_twice(direct_vm, direct_deploy):
    proof = _policy(_proof(direct_deploy))
    with direct_vm.expect_revert("POLICY_SEALED"):
        proof.seal_policy()


def test_opening_a_policy_requires_a_seal(direct_vm, direct_deploy):
    proof = _proof(direct_deploy)
    proof.add_group("root", "", "AND")
    proof.add_item("soc", "root", "a SOC 2 report", "")
    with direct_vm.expect_revert("POLICY_OPEN"):
        proof.open_policy()


def test_a_new_version_marks_earlier_verdicts_stale(direct_vm, direct_deploy):
    """The steward's first correction: no stale pass after a later policy edit."""
    proof = _policy(_proof(direct_deploy))
    proof.register_case("v2", FULL)
    direct_vm.mock_llm(PROMPT, _say(("soc2", SOC2_Q), ("dpa", DPA_Q)))
    assert proof.assess("v2") == "ELIGIBLE"
    assert proof.is_eligible("v2") is True

    proof.open_policy()
    proof.add_item("pentest", "qualified", "an annual penetration test", "")
    proof.seal_policy()

    assert proof.current_version() == 2
    assert proof.verdict_of("v2") == "ELIGIBLE"      # the record is unchanged
    assert proof.policy_version_of("v2") == 1        # bound to version 1
    assert proof.is_stale("v2") is True
    assert proof.is_eligible("v2") is False          # the gate fails closed


def test_an_open_draft_does_not_change_the_effective_policy(direct_vm, direct_deploy):
    """Between open_policy and the next seal, the last sealed version is still the one."""
    proof = _policy(_proof(direct_deploy))
    proof.register_case("v5", FULL)
    direct_vm.mock_llm(PROMPT, _say(("soc2", SOC2_Q), ("dpa", DPA_Q)))
    assert proof.assess("v5") == "ELIGIBLE"

    proof.open_policy()
    proof.add_item("pentest", "qualified", "an annual penetration test", "")
    proof.register_case("v6", FULL)

    assert proof.is_open() is True
    assert proof.current_version() == 2
    assert proof.tree() == proof.tree_of(1)
    assert proof.is_eligible("v5") is True
    assert proof.is_stale("v5") is False
    with direct_vm.expect_revert("POLICY_NOT_SEALED"):
        proof.assess("v6")


def test_a_new_version_is_evaluated_with_the_leaves_it_contains(
    direct_vm, direct_deploy
):
    """Version 1 is untouched; version 2 requires the leaf that was added later."""
    proof = _policy(_proof(direct_deploy))
    proof.open_policy()
    proof.add_item("pentest", "qualified", "an annual penetration test", "")
    proof.seal_policy()

    assert "pentest" not in proof.tree_of(1)
    assert "pentest" in proof.tree_of(2)
    assert proof.tree() == proof.tree_of(2)
    assert proof.node_version_of("soc2") == 1
    assert proof.node_version_of("pentest") == 2
    assert proof.leaf_count() == 5

    proof.register_case("v3", FULL)
    direct_vm.mock_llm(PROMPT, _say(("soc2", SOC2_Q), ("dpa", DPA_Q)))
    assert proof.assess("v3") == "MISSING"
    assert proof.missing_of("v3") == "pentest"
    assert proof.policy_version_of("v3") == 2
    assert proof.is_eligible("v3") is False


def test_sealing_publishes_the_canonical_tree(direct_vm, direct_deploy):
    proof = _proof(direct_deploy)
    proof.add_group("root", "", "AND")
    proof.add_item("b_leaf", "root", "second leaf", "")
    proof.add_item("a_leaf", "root", "first leaf", "")
    canonical = proof.seal_policy()

    assert canonical == "a_leaf:ITEM:root|b_leaf:ITEM:root|root:AND:"
    assert proof.tree_of(1) == canonical
    assert proof.is_open() is False
    assert proof.config() == "vendor-policy|3|2|v1|sealed"


def test_tree_of_an_unsealed_version_is_empty(direct_vm, direct_deploy):
    proof = _policy(_proof(direct_deploy))
    assert proof.tree_of(2) == ""


# --------------------------------------------------------------- leaf bound
def test_the_forty_first_leaf_is_refused(direct_vm, direct_deploy):
    """The steward's second correction: the limit is enforced where policies are built."""
    proof = _proof(direct_deploy)
    proof.add_group("root", "", "AND")
    for i in range(40):
        proof.add_item("l" + str(i).zfill(2), "root", "requirement number " + str(i), "")

    assert proof.leaf_count() == 40
    with direct_vm.expect_revert("TOO_MANY_LEAVES"):
        proof.add_item("l40", "root", "the leaf that does not fit", "")


def test_a_forty_leaf_policy_can_be_sealed_and_read(direct_vm, direct_deploy):
    proof = _proof(direct_deploy)
    proof.add_group("root", "", "AND")
    for i in range(40):
        proof.add_item("l" + str(i).zfill(2), "root", "requirement number " + str(i), "")
    proof.seal_policy()
    proof.register_case("v4", "This evidence contains only one of the forty items.")
    direct_vm.mock_llm(PROMPT, _say(("l07", "this evidence contains only one")))

    assert proof.assess("v4") == "MISSING"
    assert proof.met_of("v4") == "l07"
    assert proof.counts_of("v4").endswith(",39")


# --------------------------------------------------------------------- the gate
def test_gate_fails_closed_for_an_unknown_case(direct_vm, direct_deploy):
    proof = _policy(_proof(direct_deploy))
    assert proof.is_eligible("never-seen") is False
    assert proof.is_stale("never-seen") is True
    assert proof.verdict_of("never-seen") == ""
    assert proof.policy_version_of("never-seen") == 0


def test_assessing_an_unknown_case_is_rejected(direct_vm, direct_deploy):
    proof = _policy(_proof(direct_deploy))
    with direct_vm.expect_revert("CASE_NOT_FOUND"):
        proof.assess("missing-case")


def test_a_case_cannot_be_assessed_twice(direct_vm, direct_deploy):
    proof = _policy(_proof(direct_deploy))
    proof.register_case("c24", PARTIAL)
    _none(direct_vm)
    proof.assess("c24")
    with direct_vm.expect_revert("ALREADY_ASSESSED"):
        proof.assess("c24")


# ------------------------------------------------------------------- the policy
def test_only_the_owner_edits_the_policy(direct_vm, direct_deploy, direct_alice):
    proof = _proof(direct_deploy)
    with direct_vm.prank(direct_alice):
        with direct_vm.expect_revert("NOT_OWNER"):
            proof.add_group("root", "", "AND")


def test_only_the_owner_seals_and_opens_the_policy(
    direct_vm, direct_deploy, direct_alice
):
    proof = _policy(_proof(direct_deploy))
    with direct_vm.prank(direct_alice):
        with direct_vm.expect_revert("NOT_OWNER"):
            proof.open_policy()


def test_duplicate_codes_are_rejected(direct_vm, direct_deploy):
    proof = _proof(direct_deploy)
    proof.add_group("root", "", "AND")
    proof.add_item("soc2", "root", "another SOC 2 report", "")
    with direct_vm.expect_revert("NODE_EXISTS"):
        proof.add_item("soc2", "root", "a duplicate code", "")


def test_an_unknown_parent_is_rejected(direct_vm, direct_deploy):
    proof = _proof(direct_deploy)
    with direct_vm.expect_revert("UNKNOWN_PARENT"):
        proof.add_item("leaf", "nowhere", "a leaf with no parent", "")


def test_a_leaf_cannot_be_a_parent(direct_vm, direct_deploy):
    proof = _proof(direct_deploy)
    proof.add_group("root", "", "AND")
    proof.add_item("leaf", "root", "a leaf requirement", "")
    with direct_vm.expect_revert("PARENT_NOT_GROUP"):
        proof.add_item("child", "leaf", "a child under a leaf", "")


def test_only_one_root_is_allowed(direct_vm, direct_deploy):
    proof = _proof(direct_deploy)
    proof.add_group("root", "", "AND")
    with direct_vm.expect_revert("ROOT_EXISTS"):
        proof.add_group("second", "", "OR")


def test_an_invalid_mode_is_rejected(direct_vm, direct_deploy):
    proof = _proof(direct_deploy)
    with direct_vm.expect_revert("BAD_MODE"):
        proof.add_group("root", "", "XOR")


def test_sealing_without_a_tree_is_rejected(direct_vm, direct_deploy):
    proof = _proof(direct_deploy)
    with direct_vm.expect_revert("NO_TREE"):
        proof.seal_policy()


def test_sealing_without_leaves_is_rejected(direct_vm, direct_deploy):
    proof = _proof(direct_deploy)
    proof.add_group("root", "", "AND")
    proof.add_group("empty", "root", "OR")
    with direct_vm.expect_revert("NO_ITEMS"):
        proof.seal_policy()


def test_an_empty_group_blocks_sealing(direct_vm, direct_deploy):
    proof = _proof(direct_deploy)
    proof.add_group("root", "", "AND")
    proof.add_item("leaf", "root", "a leaf requirement", "")
    proof.add_group("dangling", "root", "OR")
    with direct_vm.expect_revert("EMPTY_GROUP"):
        proof.seal_policy()


# ------------------------------------------------------------------ registration
def test_short_evidence_is_rejected(direct_vm, direct_deploy):
    proof = _policy(_proof(direct_deploy))
    with direct_vm.expect_revert("BAD_TEXT"):
        proof.register_case("c25", "too short")


def test_a_case_cannot_be_registered_twice(direct_vm, direct_deploy):
    proof = _policy(_proof(direct_deploy))
    proof.register_case("c26", PARTIAL)
    with direct_vm.expect_revert("CASE_EXISTS"):
        proof.register_case("c26", FULL)


def test_a_bad_case_id_is_rejected(direct_vm, direct_deploy):
    proof = _policy(_proof(direct_deploy))
    with direct_vm.expect_revert("BAD_CASE_ID"):
        proof.register_case("bad id!", PARTIAL)


# ------------------------------------------------------------------------ views
def test_tree_views_describe_the_policy(direct_vm, direct_deploy):
    proof = _policy(_proof(direct_deploy))
    assert proof.root_of() == "qualified"
    assert proof.node_count() == 6
    assert proof.leaf_count() == 4
    assert proof.node_mode_of("enc") == "OR"
    assert proof.node_mode_of("aes") == "ITEM"
    assert proof.parent_of("aes") == "enc"
    assert proof.node_label_of("dpa") == "a signed data processing agreement"
    assert proof.node_keyword_of("aes") == "aes 256"
    assert proof.node_keyword_of("hsm") == ""
    assert proof.site_name() == "vendor-policy"
    assert proof.config() == "vendor-policy|6|4|v1|sealed"
    assert proof.current_version() == 1
    assert proof.is_open() is False
    assert proof.case_count() == 0


def test_registering_a_case_does_not_decide_anything(direct_vm, direct_deploy):
    proof = _policy(_proof(direct_deploy))
    proof.register_case("c27", FULL)
    assert proof.text_of("c27") == FULL
    assert proof.verdict_of("c27") == ""
    assert proof.is_eligible("c27") is False
    assert proof.policy_version_of("c27") == 0
