from __future__ import annotations

import json
from datetime import datetime

from app.db.models import FactArticle, FactContentScreening, FactLLMQueue, FactLLMRun, FactProductArticle
from app.llm.base import LLMProvider, LLMResponse
from app.llm.router import LLMRouter
from app.services.extract_service import ExtractService
from app.services.llm_execution_guard_service import LLMExecutionGuardService
from app.utils.hashing import sha256_text


class FakeProvider(LLMProvider):
    provider_name = "fake"

    def __init__(self, *, provider: str = "gemini", model: str = "fake-model", risky: bool = False) -> None:
        self.provider_name = provider
        self.model = model
        self.risky = risky
        self.extract_calls = 0
        self.verify_calls = 0
        self.extract_inputs: list[str] = []
        self.verify_inputs: list[str] = []

    def extract_product_info(self, input_text: str, schema: dict | None, prompt_version: str) -> LLMResponse:
        self.extract_calls += 1
        self.extract_inputs.append(input_text)
        output = _extraction_payload(with_max_amount=self.risky)
        return LLMResponse(
            provider=self.provider_name,
            model_name=self.model,
            task_type="extract",
            output_json=output,
            raw_text=json.dumps(output, ensure_ascii=False),
            token_input=100,
            token_output=50,
            cost_estimate=0.001,
        )

    def verify_extraction(self, input_text: str, extracted_json: dict, schema: dict | None, prompt_version: str) -> LLMResponse:
        self.verify_calls += 1
        self.verify_inputs.append(input_text)
        output = {
            "verification_status": "pass",
            "field_checks": [],
            "unsupported_fields": [],
            "inferred_fields": [],
            "corrected_fields": [],
            "overall_confidence": 0.95,
            "needs_human_review": False,
            "recommended_action": "save",
        }
        return LLMResponse(
            provider=self.provider_name,
            model_name=self.model,
            task_type="verify",
            output_json=output,
            raw_text=json.dumps(output, ensure_ascii=False),
            token_input=100,
            token_output=20,
            cost_estimate=0.001,
        )

    def adjudicate_conflict(self, input_text: str, extraction_a: dict, extraction_b: dict, verification_result: dict) -> LLMResponse:
        raise AssertionError("adjudicate should not be called in guard tests")


def _router(extractor: FakeProvider, verifier: FakeProvider | None = None) -> LLMRouter:
    providers: dict[str, LLMProvider] = {"gemini": extractor}
    if verifier:
        providers["qwen"] = verifier
    return LLMRouter(providers=providers)


def _article(title: str, description: str, url: str) -> FactArticle:
    return FactArticle(
        source_api="naver",
        title=title,
        description=description,
        url=url,
        original_url=url,
        pub_date=datetime(2026, 1, 10),
        content_hash=sha256_text(url),
        extraction_status="pending",
    )


def _extraction_payload(*, with_max_amount: bool = False) -> dict:
    coverage = {
        "coverage_name_raw": "질병 보장",
        "coverage_name_normalized": "질병 보장",
        "risk_area": "질병",
        "benefit_type": "unknown",
        "coverage_summary": "질병을 보장합니다.",
        "detail_level": "coverage_group",
        "evidence_text": "질병을 보장합니다.",
        "confidence": 0.9,
    }
    if with_max_amount:
        coverage["max_amount_krw"] = 10_000_000
    return {
        "article_relevance": {"is_relevant": True, "relevance_type": "new_product", "reason": "launch"},
        "products": [
            {
                "identity": {
                    "raw_product_name": "안심건강보험",
                    "normalized_product_name_candidate": "안심건강보험",
                    "company_name_raw": "삼성화재",
                    "company_name_candidate": "삼성화재",
                    "insurance_type": "손해보험",
                    "release_year_month": "2026-01",
                    "release_year_month_basis": "explicit_in_article",
                },
                "product_type_classification": {
                    "primary_product_type": {
                        "code": "HEALTH_COMPREHENSIVE",
                        "name_ko": "건강(종합)",
                        "basis": "rule",
                        "evidence_text": "건강보험",
                        "confidence": 0.9,
                    },
                    "secondary_product_types": [],
                    "needs_human_review": False,
                },
                "structured_features": {},
                "narrative_insights": {"feature_summary": "건강보험 신상품입니다."},
                "missing_fields": [],
                "major_coverages": [coverage] if with_max_amount else [],
                "sales_metrics": [],
                "evidence": {
                    "product_name_evidence": "'안심건강보험' 신규 출시",
                    "company_evidence": "삼성화재",
                    "release_date_evidence": "2026년 1월",
                    "coverage_evidence": "질병을 보장합니다." if with_max_amount else None,
                },
                "confidence": {
                    "identity": 0.95,
                    "product_type": 0.9,
                    "features": 0.9,
                    "coverage": 0.9,
                    "sales": 0.9,
                    "narrative": 0.9,
                },
                "needs_human_review": False,
            }
        ],
    }


def test_article_extraction_does_not_create_same_product_llm_run(db_session, monkeypatch):
    monkeypatch.setenv("LLM_VERIFY_ONLY_RISKY", "true")
    extractor = FakeProvider(provider="gemini")
    service = ExtractService(router=_router(extractor, FakeProvider(provider="qwen")))
    article = _article("삼성화재, '안심건강보험' 신규 출시", "삼성화재가 '안심건강보험'을 신규 출시했다.", "https://guard/a")
    db_session.add(article)
    db_session.commit()

    result = service.extract_article(db_session, article.article_id)

    assert result["status"] == "saved"
    assert extractor.extract_calls == 1
    assert db_session.query(FactLLMRun).filter(FactLLMRun.task_type == "product_consolidation").count() == 0


def test_low_skip_article_never_enqueues_or_calls_provider(db_session, monkeypatch):
    monkeypatch.setenv("LLM_SKIP_LOW_RELEVANCE", "true")
    extractor = FakeProvider(provider="gemini")
    service = ExtractService(router=_router(extractor))
    article = _article("주말 여행 후기", "맛집과 카페를 소개하는 일반 블로그 글", "https://guard/skip")
    db_session.add(article)
    db_session.commit()

    result = service.extract_article(db_session, article.article_id)

    assert result["status"] == "screened_skip"
    assert extractor.extract_calls == 0
    assert db_session.query(FactLLMQueue).count() == 0
    assert db_session.query(FactContentScreening).filter(FactContentScreening.article_id == article.article_id).count() == 1


def test_snippet_only_input_uses_snippet_bundle_and_truncates(db_session, monkeypatch):
    monkeypatch.setenv("ENABLE_PRODUCT_CLUSTER_EXTRACTION", "false")
    monkeypatch.setenv("LLM_USE_SNIPPETS_ONLY", "true")
    monkeypatch.setenv("LLM_MAX_INPUT_CHARS", "400")
    extractor = FakeProvider(provider="gemini")
    service = ExtractService(router=_router(extractor))
    article = _article(
        "삼성화재, '안심건강보험' 신규 출시",
        "삼성화재가 '안심건강보험'을 신규 출시했다. 이 상품은 질병을 보장한다. " + "본문전체 " * 200,
        "https://guard/snippet",
    )
    db_session.add(article)
    db_session.commit()

    service.extract_article(db_session, article.article_id)

    assert extractor.extract_inputs
    prompt = extractor.extract_inputs[0]
    assert '"snippets"' in prompt
    assert "안심건강보험" in prompt
    assert len(prompt) <= 400


def test_cluster_extraction_reuses_extracted_cluster_without_new_queue_or_provider_call(db_session, monkeypatch):
    monkeypatch.setenv("LLM_VERIFY_ONLY_RISKY", "true")
    extractor = FakeProvider(provider="gemini")
    service = ExtractService(router=_router(extractor, FakeProvider(provider="qwen")))
    first = _article("삼성화재, '안심건강보험' 신규 출시", "'안심건강보험'을 신규 출시했다.", "https://guard/cluster-a")
    second = _article("삼성화재 안심건강보험 출시", "삼성화재가 안심건강보험을 선보였다.", "https://guard/cluster-b")
    db_session.add_all([first, second])
    db_session.commit()

    first_result = service.extract_article(db_session, first.article_id)
    queue_count_after_first = db_session.query(FactLLMQueue).count()
    second_result = service.extract_article(db_session, second.article_id)

    assert first_result["status"] == "saved"
    assert second_result["status"] == "cluster_extracted"
    assert extractor.extract_calls == 1
    assert db_session.query(FactLLMQueue).count() == queue_count_after_first
    assert db_session.query(FactProductArticle).filter(FactProductArticle.article_id == second.article_id).count() >= 1


def test_verify_only_risky_and_verify_cache(db_session, monkeypatch):
    monkeypatch.setenv("LLM_VERIFY_ONLY_RISKY", "true")
    safe_extractor = FakeProvider(provider="gemini", risky=False)
    safe_verifier = FakeProvider(provider="qwen")
    safe_service = ExtractService(router=_router(safe_extractor, safe_verifier))
    safe_service._run_pipeline_with_cache(db_session, "삼성화재 안심건강보험 신규 출시", screening=None)
    assert safe_verifier.verify_calls == 0

    risky_extractor = FakeProvider(provider="gemini", risky=True)
    risky_verifier = FakeProvider(provider="qwen")
    risky_service = ExtractService(router=_router(risky_extractor, risky_verifier))
    risky_input = "삼성화재 안심건강보험 최대 1000만원 보장 신규 출시"
    risky_service._run_pipeline_with_cache(db_session, risky_input, screening=None)
    risky_service._run_pipeline_with_cache(db_session, risky_input, screening=None)

    assert risky_extractor.extract_calls == 1
    assert risky_verifier.verify_calls == 1


def test_llm_execution_guard_summary_reports_violations(db_session):
    article = _article("주말 여행 후기", "일반 글", "https://guard/summary")
    db_session.add(article)
    db_session.flush()
    db_session.add(
        FactContentScreening(
            article_id=article.article_id,
            source_type="naver",
            rule_relevance_score=0.0,
            llm_priority="skip",
            llm_required_yn=False,
            is_candidate=False,
        )
    )
    db_session.add(
        FactLLMRun(
            article_id=article.article_id,
            task_type="extract",
            provider="gemini",
            model_name="fake",
            input_chars=100,
            output_json="{}",
        )
    )
    db_session.add(
        FactLLMRun(
            article_id=article.article_id,
            task_type="product_consolidation",
            provider="gemini",
            model_name="fake",
            input_chars=100,
            output_json="{}",
        )
    )
    db_session.commit()

    summary = LLMExecutionGuardService().summary(db_session)

    assert summary["low_skip_llm_violation_count"] >= 1
    assert summary["article_level_same_product_llm_violation_count"] == 1
