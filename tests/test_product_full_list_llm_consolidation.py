from __future__ import annotations

from datetime import datetime

from app.db.models import DimCompany, DimProduct, DimProductAlias, FactLLMRun
from app.db.models import FactArticle, FactProductArticle
from app.llm.base import LLMResponse
from app.services.product_full_list_consolidation_service import ProductFullListConsolidationService
from app.services.product_llm_consolidation_service import ProductLLMConsolidationService
from app.utils.hashing import article_dedup_hash


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


def test_article_scope_qwen_consolidation_only_reviews_selected_products(db_session):
    company = _company(db_session, "iM라이프생명")
    canonical = _product(db_session, company, "iM스타트PRO변액연금보험", product_id=1)
    duplicate = _product(db_session, company, "스타트PRO 변액연금", product_id=2)
    outside_scope = _product(db_session, company, "iM마스터PRO변액연금보험", product_id=3)
    article = FactArticle(
        source_api="test",
        title="iM라이프생명, 스타트PRO 변액연금보험 출시",
        description="iM스타트PRO변액연금보험의 보장과 수익구조를 소개했다.",
        publisher="test",
        url="https://example.com/im-start-pro",
        original_url="https://example.com/im-start-pro",
        pub_date=datetime(2026, 6, 3),
        content_hash=article_dedup_hash("https://example.com/im-start-pro", "iM라이프생명, 스타트PRO 변액연금보험 출시", ""),
        extraction_status="cluster_extracted",
    )
    db_session.add(article)
    db_session.flush()
    db_session.add_all(
        [
            FactProductArticle(product_id=canonical.product_id, article_id=article.article_id, extraction_status="saved"),
            FactProductArticle(product_id=duplicate.product_id, article_id=article.article_id, extraction_status="saved"),
        ]
    )
    db_session.commit()

    provider = MockCompanyListProvider(
        {
            "merge_groups": [
                {
                    "canonical_id": canonical.product_id,
                    "canonical_name": canonical.normalized_product_name,
                    "merge_ids": [duplicate.product_id],
                    "confidence": 0.94,
                    "reason": "같은 기사와 같은 회사에서 언급된 축약명 변형",
                }
            ],
            "alias_cleanup": [],
            "review_items": [],
        }
    )
    llm_service = ProductLLMConsolidationService(providers={"qwen": provider}, provider_name="qwen", model_name="qwen-test")
    service = ProductFullListConsolidationService(llm_service=llm_service)

    result = service.run_article_scope_consolidation(
        db_session,
        mode="apply",
        date_from="2026-06-01",
        date_to="2026-06-09",
        force_enabled=True,
    )

    db_session.refresh(duplicate)
    db_session.refresh(outside_scope)
    assert result["product_id_count"] == 2
    assert result["auto_apply_count"] == 1
    assert provider.calls == 1
    assert "abbreviation" in provider.prompts[0]
    assert duplicate.product_status == "merged"
    assert duplicate.merged_into_product_id == canonical.product_id
    assert outside_scope.product_status == "active"


def test_high_confidence_qwen_context_variant_can_pass_soft_conflicts(db_session):
    company = _company(db_session, "DB손해보험")
    canonical = _product(
        db_session,
        company,
        "보행자사고 변호사자문비용 특약",
        product_id=1,
        product_type="ACCIDENT_DRIVER",
    )
    duplicate = _product(
        db_session,
        company,
        "보행자사고 변호사 자문 특약",
        product_id=2,
        product_type="AUTO",
    )
    service = ProductFullListConsolidationService()
    candidates = service.blocking_service._load_candidates(db_session, target="all", limit=0)
    group = {"group_key": "company:db", "company_id": company.company_id, "company_name": company.company_name_normalized, "candidates": candidates}

    rows = service.validate_product_merge_plan(
        db_session,
        group,
        {
            "merge_groups": [
                {
                    "canonical_id": canonical.product_id,
                    "canonical_name": canonical.normalized_product_name,
                    "merge_ids": [duplicate.product_id],
                    "confidence": 0.9,
                    "reason": "같은 보행자사고 변호사 자문 특약의 축약·표기 변형이며 한문철 변호사 기사 맥락도 동일함",
                }
            ],
            "alias_cleanup": [],
            "review_items": [],
        },
    )

    assert rows[0]["action"] == "auto_apply"
    assert "product type conflict" in rows[0]["review_reason"]


def test_high_confidence_qwen_merge_still_rejects_product_class_conflict(db_session):
    company = _company(db_session, "DB생명")
    term = _product(db_session, company, "무 AI 라이프케어 정기보험", product_id=1, product_type="DEATH_WHOLELIFE")
    cancer = _product(db_session, company, "AI 라이프케어 암보험", product_id=2, product_type="CANCER")
    service = ProductFullListConsolidationService()
    candidates = service.blocking_service._load_candidates(db_session, target="all", limit=0)
    group = {"group_key": "company:db-life", "company_id": company.company_id, "company_name": company.company_name_normalized, "candidates": candidates}

    rows = service.validate_product_merge_plan(
        db_session,
        group,
        {
            "merge_groups": [
                {
                    "canonical_id": term.product_id,
                    "canonical_name": term.normalized_product_name,
                    "merge_ids": [cancer.product_id],
                    "confidence": 0.95,
                    "reason": "같은 AI 라이프케어 기사에 등장한 상품명 변형",
                }
            ],
            "alias_cleanup": [],
            "review_items": [],
        },
    )

    assert rows[0]["action"] == "review"
    assert "product class conflict" in rows[0]["review_reason"]


def test_primary_product_class_conflict_ignores_mixed_alias_leakage(db_session):
    company = _company(db_session, "DB생명")
    term = _product(db_session, company, "무 AI 라이프케어 정기보험", product_id=1, product_type="DEATH_WHOLELIFE")
    cancer = _product(db_session, company, "AI 라이프케어 암보험", product_id=2, product_type="CANCER")
    db_session.add(
        DimProductAlias(
            product_id=cancer.product_id,
            raw_product_name="AI 라이프케어 정기 보험",
            normalized_product_name_candidate="AI 라이프케어 정기보험",
            product_core_key="ai라이프케어정기보험",
            company_id=company.company_id,
            source_type="official_name",
        )
    )
    db_session.flush()
    service = ProductFullListConsolidationService()
    candidates = service.blocking_service._load_candidates(db_session, target="all", limit=0)
    group = {"group_key": "company:db-life", "company_id": company.company_id, "company_name": company.company_name_normalized, "candidates": candidates}

    rows = service.validate_product_merge_plan(
        db_session,
        group,
        {
            "merge_groups": [
                {
                    "canonical_id": term.product_id,
                    "canonical_name": term.normalized_product_name,
                    "merge_ids": [cancer.product_id],
                    "confidence": 0.95,
                    "reason": "같은 AI 라이프케어 기사에 등장한 상품명 변형",
                }
            ],
            "alias_cleanup": [],
            "review_items": [],
        },
    )

    assert rows[0]["action"] == "review"
    assert "product class conflict" in rows[0]["review_reason"]


def test_high_confidence_qwen_5n5_variant_can_pass_family_conflict(db_session):
    company = _company(db_session, "NH농협손해보험")
    canonical = _product(db_session, company, "5.N.5 건강보험", product_id=1, product_type="HEALTH_COMPREHENSIVE")
    duplicate = _product(db_session, company, "NH5.N.5굿플러스건강보험 1040형", product_id=2, product_type="HEALTH_COMPREHENSIVE")
    service = ProductFullListConsolidationService()
    candidates = service.blocking_service._load_candidates(db_session, target="all", limit=0)
    group = {"group_key": "company:nh", "company_id": company.company_id, "company_name": company.company_name_normalized, "candidates": candidates}

    rows = service.validate_product_merge_plan(
        db_session,
        group,
        {
            "merge_groups": [
                {
                    "canonical_id": canonical.product_id,
                    "canonical_name": canonical.normalized_product_name,
                    "merge_ids": [duplicate.product_id],
                    "confidence": 0.9,
                    "reason": "5.N.5와 NH5.N.5굿플러스는 같은 건강보험 제품군의 공식명·서브네임 변형",
                }
            ],
            "alias_cleanup": [],
            "review_items": [],
        },
    )

    assert rows[0]["action"] == "auto_apply"


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
