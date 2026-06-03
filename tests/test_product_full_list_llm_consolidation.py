from __future__ import annotations

from app.db.models import DimCompany, DimProduct, FactLLMRun
from app.llm.base import LLMResponse
from app.services.product_full_list_consolidation_service import ProductFullListConsolidationService
from app.services.product_llm_consolidation_service import ProductLLMConsolidationService


class MockCompanyListProvider:
    provider_name = "gemini"
    model_name = "gemini-2.5-flash"

    def __init__(self, output_json: dict) -> None:
        self.output_json = output_json
        self.calls = 0
        self.prompts: list[str] = []

    def judge_consolidation_block(self, prompt: str, task_type: str) -> LLMResponse:
        self.calls += 1
        self.prompts.append(prompt)
        return LLMResponse(
            provider="gemini",
            model_name=self.model_name,
            task_type=task_type,
            output_json=self.output_json,
            raw_text="{}",
            token_input=120,
            token_output=40,
        )

    def extract_product_info(self, input_text, schema, prompt_version):  # pragma: no cover
        raise AssertionError("article extraction must not be used")

    def verify_extraction(self, input_text, extracted_json, schema, prompt_version):  # pragma: no cover
        raise AssertionError("verification must not be used")

    def adjudicate_conflict(self, input_text, extraction_a, extraction_b, verification_result):  # pragma: no cover
        raise AssertionError("adjudication must not be used")


def _company(db_session, name: str) -> DimCompany:
    row = DimCompany(company_name_normalized=name, insurance_type="life", include_in_product_news_default="Y")
    db_session.add(row)
    db_session.flush()
    return row


def _product(db_session, company: DimCompany, name: str, *, product_id: int, product_type: str = "ANNUITY_SAVINGS") -> DimProduct:
    row = DimProduct(
        product_id=product_id,
        normalized_product_name=name,
        raw_product_name=name,
        product_search_key=f"{company.company_id}:{name}:{product_id}",
        product_core_key=name.replace(" ", "").casefold(),
        company_id=company.company_id,
        insurance_type=company.insurance_type,
        release_year_month="2026-01",
        primary_product_type_code=product_type,
        product_status="active",
        confidence_total=0.9,
        needs_review=False,
    )
    db_session.add(row)
    db_session.flush()
    return row


def test_full_list_llm_merge_applies_valid_same_company_plan(db_session, monkeypatch):
    monkeypatch.setenv("PRODUCT_LLM_CONSOLIDATION_ENABLED", "true")
    company = _company(db_session, "Shinhan Life")
    canonical = _product(db_session, company, "Tontine annuity insurance", product_id=1)
    duplicate = _product(db_session, company, "Korean Tontine annuity", product_id=2)
    db_session.commit()

    provider = MockCompanyListProvider(
        {
            "merge_groups": [
                {
                    "canonical_id": canonical.product_id,
                    "canonical_name": canonical.normalized_product_name,
                    "merge_ids": [duplicate.product_id],
                    "confidence": 0.94,
                    "reason": "same insurer and tontine annuity family",
                }
            ],
            "alias_cleanup": [],
            "review_items": [],
        }
    )
    llm_service = ProductLLMConsolidationService(providers={"gemini": provider})
    service = ProductFullListConsolidationService(llm_service=llm_service)

    dry_run = service.run_full_list_consolidation(db_session, mode="dry_run", target="all")
    assert dry_run["auto_apply_count"] == 1
    assert provider.calls == 1
    db_session.refresh(duplicate)
    assert duplicate.product_status == "active"

    # Same prompt should be cached on the second dry-run.
    cached = service.run_full_list_consolidation(db_session, mode="dry_run", target="all")
    assert cached["llm_call_count"] == 0
    assert provider.calls == 1
    assert db_session.query(FactLLMRun).filter(FactLLMRun.task_type == "product_list_consolidation", FactLLMRun.cached_yn.is_(True)).count() >= 1

    applied = service.run_full_list_consolidation(db_session, mode="apply", target="all")
    db_session.refresh(duplicate)
    assert applied["auto_apply_count"] == 1
    assert duplicate.product_status == "merged"
    assert duplicate.merged_into_product_id == canonical.product_id


def test_full_list_validator_rejects_cross_company_merge(db_session, monkeypatch):
    monkeypatch.setenv("PRODUCT_LLM_CONSOLIDATION_ENABLED", "true")
    left_company = _company(db_session, "Shinhan Life")
    right_company = _company(db_session, "Other Life")
    left = _product(db_session, left_company, "Tontine annuity insurance", product_id=1)
    right = _product(db_session, right_company, "Tontine annuity insurance", product_id=2)

    service = ProductFullListConsolidationService()
    candidates = service.blocking_service._load_candidates(db_session, target="all", limit=0)
    group = {"group_key": "manual-cross-company", "company_id": None, "company_name": None, "candidates": candidates}
    rows = service.validate_product_merge_plan(
        db_session,
        group,
        {
            "merge_groups": [
                {
                    "canonical_id": left.product_id,
                    "canonical_name": left.normalized_product_name,
                    "merge_ids": [right.product_id],
                    "confidence": 0.99,
                    "reason": "bad merge",
                }
            ]
        },
    )

    assert rows[0]["action"] == "review"
    assert "known company differs" in rows[0]["review_reason"]


def test_alias_cleanup_marks_different_product_family_for_review(db_session):
    company = _company(db_session, "ABL Life")
    product = _product(db_session, company, "WON health refund insurance", product_id=1, product_type="HEALTH_COMPREHENSIVE")
    service = ProductFullListConsolidationService()
    candidates = service.blocking_service._load_candidates(db_session, target="all", limit=0)
    group = {"group_key": "company:abl", "company_id": company.company_id, "company_name": company.company_name_normalized, "candidates": candidates}

    rows = service.validate_product_merge_plan(
        db_session,
        group,
        {
            "merge_groups": [],
            "alias_cleanup": [
                {
                    "product_id": product.product_id,
                    "alias_name": "whole body anesthesia surgery insurance",
                    "confidence": 0.9,
                    "reason": "different surgery product family",
                }
            ],
        },
    )

    assert rows[0]["item_type"] == "alias_cleanup"
    assert rows[0]["action"] == "alias_cleanup_review"

