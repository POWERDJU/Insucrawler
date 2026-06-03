from datetime import datetime

from app.db.models import DimCompany, DimProduct, FactArticle
from app.extractors.extraction_schema import ExtractionResult
from app.services.extract_service import ExtractService
from app.utils.hashing import sha256_text


def make_article(db_session, suffix: str, text: str) -> FactArticle:
    article = FactArticle(
        source_api="unit",
        title=text,
        description=text,
        url=f"https://example.test/reconcile/{suffix}",
        content_hash=sha256_text(f"https://example.test/reconcile/{suffix}"),
        pub_date=datetime(2026, 1, 10),
        extraction_status="pending",
    )
    db_session.add(article)
    db_session.flush()
    return article


def extraction_payload(company_candidate: str) -> ExtractionResult:
    return ExtractionResult.model_validate(
        {
            "article_relevance": {"is_relevant": True, "relevance_type": "new_product", "reason": "unit"},
            "products": [
                {
                    "identity": {
                        "raw_product_name": "농업인 안전보험",
                        "normalized_product_name_candidate": "농업인 안전보험",
                        "company_name_raw": company_candidate,
                        "company_name_candidate": company_candidate,
                        "insurance_type": "unknown",
                        "release_year_month": None,
                        "release_year_month_basis": "unknown",
                    },
                    "product_type_classification": {
                        "primary_product_type": {"code": "OTHER", "name_ko": "기타", "basis": "unit", "evidence_text": "농업인 안전보험", "confidence": 0.6},
                        "secondary_product_types": [],
                        "needs_human_review": False,
                    },
                    "evidence": {"product_name_evidence": "농업인 안전보험", "company_evidence": company_candidate},
                    "confidence": {"identity": 0.6, "product_type": 0.6, "features": 0.0, "coverage": 0.0, "sales": 0.0, "narrative": 0.0},
                    "needs_human_review": False,
                }
            ],
        }
    )


def test_unknown_company_candidate_does_not_create_company(db_session):
    article = make_article(db_session, "unknown", "경남농협이 보험 관련 행사를 진행했다")

    product_ids = ExtractService().save_extraction_result(
        db_session,
        extraction_payload("경남농협"),
        article_id=article.article_id,
        source_text=article.title,
    )
    db_session.commit()

    assert product_ids == []
    assert db_session.query(DimProduct).count() == 0
    assert db_session.query(DimCompany).filter(DimCompany.company_name_normalized == "경남농협").count() == 0


def test_known_insurer_in_article_context_overrides_unknown_candidate(db_session):
    article = make_article(db_session, "known-context", "경남농협과 NH농협손해보험이 보험상품을 소개했다")

    [product_id] = ExtractService().save_extraction_result(
        db_session,
        extraction_payload("경남농협"),
        article_id=article.article_id,
        source_text=article.title,
    )
    db_session.commit()

    product = db_session.get(DimProduct, product_id)
    company = db_session.get(DimCompany, product.company_id)
    assert company.company_name_normalized == "NH농협손해보험"


def test_known_insurer_in_article_context_overrides_wrong_known_candidate(db_session):
    article = make_article(db_session, "wrong-known", "NH농협손해보험이 농업인 안전보험을 소개했다")

    [product_id] = ExtractService().save_extraction_result(
        db_session,
        extraction_payload("삼성화재"),
        article_id=article.article_id,
        source_text=article.title,
    )
    db_session.commit()

    product = db_session.get(DimProduct, product_id)
    company = db_session.get(DimCompany, product.company_id)
    assert company.company_name_normalized == "NH농협손해보험"
