from __future__ import annotations

from datetime import datetime

from app.db.models import (
    DimProduct,
    FactArticle,
    FactExclusiveUseRight,
    FactExclusiveUseRightArticle,
    FactExclusiveUseRightArticle,
    FactLLMBatchJob,
    FactLLMQueue,
    FactProductArticle,
    FactProductObservation,
)
from app.services.batch_llm_service import BatchLLMService
from app.services.multi_company_article_filter_service import MultiCompanyArticleFilterService
from app.services.multi_company_extraction_cleanup_service import MultiCompanyExtractionCleanupService


def _article(db, title: str, *, multi: bool = False, suffix: str = "a") -> FactArticle:
    article = FactArticle(
        source_api="test",
        title=title,
        description=title,
        url=f"https://example.com/{suffix}",
        content_hash=f"multi-company-{suffix}",
        pub_date=datetime(2026, 1, 1),
        extraction_status="extracted",
        multi_company_article_yn=multi,
    )
    db.add(article)
    db.flush()
    return article


def _product(db, name: str) -> DimProduct:
    product = DimProduct(
        normalized_product_name=name,
        raw_product_name=name,
        product_search_key=name,
        product_core_key=name,
        confidence_total=0.9,
        needs_review=False,
        product_status="active",
        insurance_type="손해보험",
    )
    db.add(product)
    db.flush()
    return product


def _exclusive(db, subject: str) -> FactExclusiveUseRight:
    event = FactExclusiveUseRight(
        subject_name=subject,
        subject_core_key=subject,
        company_name_normalized="한화손해보험",
        insurance_type="손해보험",
        exclusivity_months=6,
        acquired_year_month="2026-01",
        feature_summary="특징",
        confidence_total=0.9,
        needs_review=False,
        event_status="active",
    )
    db.add(event)
    db.flush()
    return event


def test_multi_company_article_filter_counts_only_known_insurers(db_session):
    service = MultiCompanyArticleFilterService()

    result = service.classify_text(db_session, "한화손해보험과 롯데손해보험이 각각 신상품을 출시했다.")
    assert result.is_multi_company is True
    assert set(result.company_names) == {"한화손해보험", "롯데손해보험"}

    association_result = service.classify_text(db_session, "한화손해보험과 손해보험협회가 제도 개선을 설명했다.")
    assert association_result.is_multi_company is False
    assert association_result.company_names == ["한화손해보험"]


def test_product_mixed_source_is_kept_and_only_multi_is_marked(db_session):
    multi_article = _article(db_session, "한화손해보험과 롯데손해보험 신상품 기사", multi=True, suffix="product-multi")
    clean_article = _article(db_session, "한화손해보험 단독 신상품 기사", suffix="product-clean")
    mixed_product = _product(db_session, "혼합 근거 상품")
    only_multi_product = _product(db_session, "다수보험사 기사만 있는 상품")
    db_session.add_all(
        [
            FactProductArticle(product_id=mixed_product.product_id, article_id=multi_article.article_id),
            FactProductArticle(product_id=mixed_product.product_id, article_id=clean_article.article_id),
            FactProductArticle(product_id=only_multi_product.product_id, article_id=multi_article.article_id),
            FactProductObservation(
                product_id=mixed_product.product_id,
                article_id=multi_article.article_id,
                raw_product_name="혼합 근거 상품",
                candidate_type="launch_name",
            ),
        ]
    )
    db_session.commit()

    result = MultiCompanyExtractionCleanupService().apply_product_cleanup(db_session)
    db_session.refresh(mixed_product)
    db_session.refresh(only_multi_product)

    assert result["source_records_excluded"] == 2
    assert mixed_product.product_status == "active"
    assert only_multi_product.product_status == "rejected_multi_company_only"
    assert db_session.get(FactArticle, multi_article.article_id) is not None
    link = (
        db_session.query(FactProductArticle)
        .filter_by(product_id=mixed_product.product_id, article_id=multi_article.article_id)
        .one()
    )
    clean_link = (
        db_session.query(FactProductArticle)
        .filter_by(product_id=mixed_product.product_id, article_id=clean_article.article_id)
        .one()
    )
    assert link.extraction_status == "excluded_multi_company"
    assert clean_link.extraction_status == "saved"


def test_exclusive_mixed_source_is_kept_and_only_multi_is_marked(db_session):
    multi_article = _article(db_session, "삼성생명과 삼성화재 배타적사용권 기사", multi=True, suffix="exclusive-multi")
    clean_article = _article(db_session, "삼성생명 단독 배타적사용권 기사", suffix="exclusive-clean")
    mixed_event = _exclusive(db_session, "혼합 근거 특약")
    only_multi_event = _exclusive(db_session, "다수보험사 기사만 있는 특약")
    db_session.add_all(
        [
            FactExclusiveUseRightArticle(exclusive_right_id=mixed_event.exclusive_right_id, article_id=multi_article.article_id),
            FactExclusiveUseRightArticle(exclusive_right_id=mixed_event.exclusive_right_id, article_id=clean_article.article_id),
            FactExclusiveUseRightArticle(exclusive_right_id=only_multi_event.exclusive_right_id, article_id=multi_article.article_id),
        ]
    )
    db_session.commit()

    result = MultiCompanyExtractionCleanupService().apply_exclusive_cleanup(db_session)
    db_session.refresh(mixed_event)
    db_session.refresh(only_multi_event)

    assert result["source_records_excluded"] == 2
    assert mixed_event.event_status == "active"
    assert mixed_event.article_count == 1
    assert only_multi_event.event_status == "rejected_multi_company_only"


def test_batch_import_guard_skips_multi_company_article(db_session, tmp_path):
    article = _article(db_session, "한화손해보험과 롯데손해보험 신상품 기사", multi=True, suffix="batch-multi")
    queue = FactLLMQueue(
        target_type="article",
        target_id=article.article_id,
        task_type="extract",
        priority="high",
        batch_eligible_yn=True,
        status="running",
    )
    job = FactLLMBatchJob(
        provider="gemini",
        model_name="gemini-2.0-flash",
        task_type="extract",
        status="provider_completed",
        request_count=1,
    )
    db_session.add_all([queue, job])
    db_session.flush()
    queue.llm_batch_job_id = job.llm_batch_job_id
    output = tmp_path / "batch.jsonl"
    output.write_text(
        '{"key":"%s","response":{"text":"{\\"products\\": []}"}}\n' % queue.llm_queue_id,
        encoding="utf-8",
    )
    db_session.commit()

    result = BatchLLMService().import_results(db_session, job, output)
    db_session.refresh(queue)

    assert result["skipped"] == 1
    assert queue.status == "excluded_multi_company"
