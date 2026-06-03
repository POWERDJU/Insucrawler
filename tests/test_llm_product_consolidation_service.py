from __future__ import annotations

from app.db.models import DimCompany, DimProduct, FactLLMRun
from app.llm.base import LLMResponse
from app.services.product_llm_consolidation_service import ProductLLMConsolidationService


class MockConsolidationProvider:
    provider_name = "gemini"
    model_name = "gemini-2.5-flash"

    def __init__(self) -> None:
        self.calls = 0

    def judge_consolidation_block(self, prompt: str, task_type: str) -> LLMResponse:
        self.calls += 1
        return LLMResponse(
            provider="gemini",
            model_name=self.model_name,
            task_type=task_type,
            output_json={
                "merge_groups": [
                    {
                        "canonical_id": 1,
                        "canonical_name": "신한톤틴연금보험",
                        "merge_ids": [2],
                        "confidence": 0.94,
                        "reason": "same company tontine annuity product",
                    }
                ],
                "review_items": [],
                "no_merge_items": [],
            },
            raw_text="{}",
            token_input=100,
            token_output=30,
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


def _product(db_session, company: DimCompany, name: str, product_id: int | None = None) -> DimProduct:
    product = DimProduct(
        product_id=product_id,
        normalized_product_name=name,
        raw_product_name=name,
        product_search_key=f"{company.company_id}:{name}",
        product_core_key=name.replace(" ", ""),
        company_id=company.company_id,
        insurance_type=company.insurance_type,
        release_year_month="2026-01",
        primary_product_type_code="ANNUITY_SAVINGS",
        product_status="active",
        confidence_total=0.9,
        needs_review=False,
    )
    db_session.add(product)
    db_session.flush()
    return product


def test_product_llm_merge_plan_apply_and_cache(db_session, monkeypatch):
    monkeypatch.setenv("PRODUCT_LLM_CONSOLIDATION_ENABLED", "true")
    company = _company(db_session, "신한라이프생명")
    canonical = _product(db_session, company, "신한톤틴연금보험", product_id=1)
    duplicate = _product(db_session, company, "톤틴(Tontine) 연금", product_id=2)
    db_session.commit()

    provider = MockConsolidationProvider()
    service = ProductLLMConsolidationService(providers={"gemini": provider})
    first = service.run(db_session, mode="dry_run", target="all", limit=0, max_blocks=1)
    assert first["auto_apply_count"] == 1
    assert provider.calls == 1

    # Same compact block/prompt should hit cache and avoid another provider call.
    second = service.run(db_session, mode="dry_run", target="all", limit=0, max_blocks=1)

    assert second["llm_call_count"] == 0
    assert provider.calls == 1
    assert db_session.query(FactLLMRun).filter(FactLLMRun.task_type == "product_list_consolidation", FactLLMRun.cached_yn.is_(True)).count() >= 1

    applied = service.run(db_session, mode="apply", target="all", limit=0, max_blocks=1)
    db_session.refresh(canonical)
    db_session.refresh(duplicate)
    assert applied["auto_apply_count"] == 1
    assert duplicate.product_status == "merged"
    assert duplicate.merged_into_product_id == canonical.product_id


def test_product_llm_validator_rejects_different_company(db_session, monkeypatch):
    monkeypatch.setenv("PRODUCT_LLM_CONSOLIDATION_ENABLED", "true")
    left_company = _company(db_session, "신한라이프생명")
    right_company = _company(db_session, "한화생명")
    _product(db_session, left_company, "톤틴연금보험", product_id=1)
    _product(db_session, right_company, "톤틴연금보험", product_id=2)
    db_session.commit()

    provider = MockConsolidationProvider()
    service = ProductLLMConsolidationService(providers={"gemini": provider})
    blocks = service.build_product_merge_blocks(db_session, target="all", limit=0)

    assert blocks == []
