from app.services.qwen_adjudication_service import QwenAdjudicationService


def test_qwen_priority_wins_without_hard_gate():
    choice = QwenAdjudicationService().choose_final_decision(
        rule_decision={"decision": "reject", "reason": "weak_rule", "confidence": 0.7},
        qwen_decision={"decision": "accept", "reason": "article_evidence_supported", "confidence": 0.9},
        hard_gate_errors=[],
    )

    assert choice.source == "qwen"
    assert choice.decision == "accept"


def test_hard_gate_blocks_qwen_accept():
    choice = QwenAdjudicationService().choose_final_decision(
        rule_decision={"decision": "review"},
        qwen_decision={"decision": "accept", "confidence": 0.95},
        hard_gate_errors=["company_master_absent"],
    )

    assert choice.source == "hard_gate"
    assert choice.decision == "review"
