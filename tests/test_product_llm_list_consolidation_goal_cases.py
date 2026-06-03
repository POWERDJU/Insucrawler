from __future__ import annotations

import json

from app.db.models import FactLLMRun
from app.llm.base import LLMResponse
from app.services.product_full_list_consolidation_service import ProductFullListConsolidationService
from app.services.product_llm_consolidation_service import ProductLLMConsolidationService
from tests.test_product_consolidation_goal_cases import _company, _product


class GoalMockListProvider:
    provider_name = "gemini"
    model_name = "gemini-2.5-flash"

    def __init__(self, output_json: dict) -> None:
        self.output_json = output_json
        self.calls = 0
        self.prompts: list[str] = []

    def judge_consolidation_block(self, prompt: str, task_type: str) -> LLMResponse:
        self.calls += 1
        self.prompts.append(prompt)
        assert task_type == "product_list_consolidation"
        assert "article_fulltext_reparse_for_merge" not in prompt
        assert "pairwise_product_compare" not in prompt
        return LLMResponse(
            provider="gemini",
            model_name=self.model_name,
            task_type=task_type,
            output_json=self.output_json,
            raw_text=json.dumps(self.output_json, ensure_ascii=False),
            token_input=160,
            token_output=60,
        )

    def extract_product_info(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("article extraction must not be used for product consolidation")

    def verify_extraction(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("article verification must not be used for product consolidation")

    def adjudicate_conflict(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("article adjudication must not be used for product consolidation")


def test_goal_llm_list_consolidation_mock_applies_only_valid_same_company_plan(db_session, monkeypatch):
    monkeypatch.setenv("PRODUCT_LLM_CONSOLIDATION_ENABLED", "true")
    company = _company(db_session, "\uc2e0\ud55c\ub77c\uc774\ud504\uc0dd\uba85")
    canonical = _product(db_session, company, "\uc2e0\ud55c\ud1a4\ud2f4\uc5f0\uae08\ubcf4\ud5d8", product_type="ANNUITY_SAVINGS")
    duplicate = _product(db_session, company, "\ud1a4\ud2f4(Tontine) \uc5f0\uae08", product_type="ANNUITY_SAVINGS")
    db_session.commit()

    provider = GoalMockListProvider(
        {
            "merge_groups": [
                {
                    "canonical_id": canonical.product_id,
                    "canonical_name": canonical.normalized_product_name,
                    "merge_ids": [duplicate.product_id],
                    "confidence": 0.94,
                    "reason": "same company compact-list tontine annuity variants",
                }
            ],
            "alias_cleanup": [],
            "review_items": [],
        }
    )
    llm_service = ProductLLMConsolidationService(providers={"gemini": provider})
    service = ProductFullListConsolidationService(llm_service=llm_service)

    dry_run = service.run_full_list_consolidation(db_session, mode="dry_run", target="all", max_blocks=1)
    assert dry_run["auto_apply_count"] == 1
    assert provider.calls == 1
    db_session.refresh(duplicate)
    assert duplicate.product_status != "merged"

    cached = service.run_full_list_consolidation(db_session, mode="dry_run", target="all", max_blocks=1)
    assert cached["llm_call_count"] == 0
    assert provider.calls == 1
    assert db_session.query(FactLLMRun).filter(
        FactLLMRun.task_type == "product_list_consolidation",
        FactLLMRun.cached_yn.is_(True),
    ).count() >= 1

    applied = service.run_full_list_consolidation(db_session, mode="apply", target="all", max_blocks=1)
    db_session.refresh(duplicate)
    assert applied["auto_apply_count"] == 1
    assert duplicate.product_status == "merged"
    assert duplicate.merged_into_product_id == canonical.product_id


def test_goal_llm_list_validator_rejects_health_refund_and_surgery_merge(db_session, monkeypatch):
    monkeypatch.setenv("PRODUCT_LLM_CONSOLIDATION_ENABLED", "true")
    company = _company(db_session, "ABL\uc0dd\uba85")
    health = _product(db_session, company, "\uc6b0\ub9acWON\uac74\uac15\ud658\uae09\ubcf4\ud5d8")
    surgery = _product(db_session, company, "\uc6b0\ub9acWON\uc804\uc2e0\ub9c8\ucde8\uc218\uc220\ubcf4\ud5d8")
    db_session.commit()

    service = ProductFullListConsolidationService()
    group = service.build_company_product_groups(db_session, target="all")[0]
    rows = service.validate_product_merge_plan(
        db_session,
        group,
        {
            "merge_groups": [
                {
                    "canonical_id": health.product_id,
                    "canonical_name": health.normalized_product_name,
                    "merge_ids": [surgery.product_id],
                    "confidence": 0.99,
                    "reason": "bad mock merge",
                }
            ],
            "alias_cleanup": [],
            "review_items": [],
        },
    )

    assert rows[0]["action"] == "review"
    assert "specific family conflict" in rows[0]["review_reason"]
