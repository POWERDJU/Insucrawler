from __future__ import annotations

from app.db.models import DimCompany, FactExclusiveUseRight, FactLLMRun
from app.llm.base import LLMResponse
from app.services.exclusive_right_consolidation_service import ExclusiveRightBlock
from app.services.exclusive_right_llm_consolidation_service import ExclusiveRightLLMConsolidationService


class MockExclusiveConsolidationProvider:
    provider_name = "gemini"
    model_name = "gemini-2.5-flash"

    def __init__(self, output: dict) -> None:
        self.output = output
        self.calls = 0

    def judge_consolidation_block(self, prompt: str, task_type: str) -> LLMResponse:
        self.calls += 1
        return LLMResponse(
            provider="gemini",
            model_name=self.model_name,
            task_type=task_type,
            output_json=self.output,
            raw_text="{}",
            token_input=90,
            token_output=25,
        )

    def extract_product_info(self, input_text, schema, prompt_version):  # pragma: no cover
        raise AssertionError("not used")

    def verify_extraction(self, input_text, extracted_json, schema, prompt_version):  # pragma: no cover
        raise AssertionError("not used")

    def adjudicate_conflict(self, input_text, extraction_a, extraction_b, verification_result):  # pragma: no cover
        raise AssertionError("not used")


def _company(db_session, name: str) -> DimCompany:
    company = DimCompany(company_name_normalized=name, insurance_type="생명보험", include_in_product_news_default="Y")
    db_session.add(company)
    db_session.flush()
    return company


def _exclusive(db_session, company: DimCompany, subject: str, *, months: int = 6, item_id: int | None = None) -> FactExclusiveUseRight:
    item = FactExclusiveUseRight(
        exclusive_right_id=item_id,
        company_id=company.company_id,
        company_name_normalized=company.company_name_normalized,
        insurance_type=company.insurance_type,
        subject_name=subject,
        subject_core_key=subject.replace(" ", ""),
        exclusivity_months=months,
        acquired_year_month="2026-01",
        feature_summary=f"{subject} 배타적사용권",
        evidence_summary=f"{subject} 6개월 배타적사용권 인정",
        evidence_text=f"{company.company_name_normalized}은 '{subject}'에 대해 6개월 배타적사용권을 인정받았다.",
        article_count=1,
        confidence_total=0.9,
        needs_review=False,
        event_status="active",
    )
    db_session.add(item)
    db_session.flush()
    return item


def test_exclusive_llm_validator_accepts_resolved_subject_and_cache(db_session, monkeypatch):
    monkeypatch.setenv("EXCLUSIVE_RIGHT_LLM_CONSOLIDATION_ENABLED", "true")
    company = _company(db_session, "삼성생명")
    weak = _exclusive(db_session, company, "해당 상품", item_id=1)
    strong = _exclusive(db_session, company, "돌봄 로봇 제공 서비스", item_id=2)
    db_session.commit()
    plan = {
        "merge_groups": [
            {
                "canonical_id": 2,
                "canonical_subject_name": "돌봄 로봇 제공 서비스",
                "merge_ids": [1],
                "confidence": 0.91,
                "reason": "weak reference resolves to service in evidence",
            }
        ],
        "reject_items": [],
        "review_items": [],
    }
    provider = MockExclusiveConsolidationProvider(plan)
    service = ExclusiveRightLLMConsolidationService(providers={"gemini": provider})
    block = ExclusiveRightBlock([weak, strong], "same_company_subject_context")

    llm_plan, _ = service.run_llm_exclusive_block_judge(db_session, block)
    rows = service.validate_llm_exclusive_merge_plan(db_session, block, llm_plan)
    assert rows[0]["action"] == "auto_apply"

    llm_plan_cached, run = service.run_llm_exclusive_block_judge(db_session, block)
    assert llm_plan_cached == llm_plan
    assert run.cached_yn is True
    assert provider.calls == 1
    assert db_session.query(FactLLMRun).filter(FactLLMRun.task_type == "exclusive_right_list_consolidation", FactLLMRun.cached_yn.is_(True)).count() >= 1


def test_exclusive_llm_validator_rejects_weak_canonical_and_period_conflict(db_session):
    company = _company(db_session, "삼성생명")
    weak = _exclusive(db_session, company, "해당 상품", months=6, item_id=1)
    strong = _exclusive(db_session, company, "돌봄 로봇 제공 서비스", months=3, item_id=2)
    block = ExclusiveRightBlock([weak, strong], "same_company_subject_context")
    plan = {
        "merge_groups": [
            {
                "canonical_id": 1,
                "canonical_subject_name": "해당 상품",
                "merge_ids": [2],
                "confidence": 0.92,
                "reason": "bad plan",
            }
        ]
    }
    rows = ExclusiveRightLLMConsolidationService().validate_llm_exclusive_merge_plan(db_session, block, plan)

    assert rows[0]["action"] == "review"
    assert "weak canonical subject" in rows[0]["review_reason"]
    assert "exclusivity period differs" in rows[0]["review_reason"]
