from __future__ import annotations

from datetime import datetime

from app.db.models import DimCompany, DimProduct, FactArticle, FactProductArticle
from app.normalizers.product_name_normalizer import normalize_product_family_signature, version_signature
from app.services.product_blocking_service import ProductBlockingService


def _company(db_session, name: str, insurance_type: str = "생명보험") -> DimCompany:
    row = DimCompany(
        company_name_normalized=name,
        company_name_raw=name,
        alias=name,
        insurance_type=insurance_type,
        include_in_product_news_default="Y",
        active_yn="Y",
    )
    db_session.add(row)
    db_session.flush()
    return row


def _product(db_session, company: DimCompany, name: str) -> DimProduct:
    row = DimProduct(
        raw_product_name=name,
        normalized_product_name=name,
        product_search_key=f"{company.company_id}:{name}",
        product_core_key=name.replace(" ", "").casefold(),
        company_id=company.company_id,
        insurance_type=company.insurance_type,
        release_year_month="2026-01",
        primary_product_type_code="ANNUITY_SAVINGS",
        product_status="active",
        confidence_total=0.9,
        needs_review=False,
    )
    db_session.add(row)
    db_session.flush()
    row.canonical_product_id = row.product_id
    return row


def test_family_and_version_signature_ignore_article_context(db_session):
    company = _company(db_session, "신한라이프생명")
    product = _product(db_session, company, "톤틴(Tontine) 연금")
    article = FactArticle(
        source_api="test",
        title="건강보험부터 연금·종신보험까지 새해 보험 신상품 러시 12일 1월 130만원",
        description="암, 치매, 다양한 보장을 담은 기사 설명",
        url="https://example.com/a",
        original_url="https://example.com/a",
        pub_date=datetime(2026, 1, 12),
        content_hash="family-clean-source-a",
    )
    db_session.add(article)
    db_session.flush()
    db_session.add(FactProductArticle(product_id=product.product_id, article_id=article.article_id))
    db_session.commit()

    candidate = ProductBlockingService()._load_candidates(db_session, target="all", limit=0)[0]

    assert candidate.family_signature == "톤틴연금"
    assert candidate.version_signature == set()
    assert not {"암", "치매", "12일", "1월", "130만원"}.intersection(candidate.family_tokens)


def test_version_signature_only_accepts_explicit_product_versions():
    assert version_signature("시그니처 여성 건강보험 4.0") == {"4.0"}
    assert version_signature("시그니처 여성보험 3.0") == {"3.0"}
    assert version_signature("V2 플랜") == {"v2"}
    assert version_signature("2세대 보험") == {"2세대"}
    assert version_signature("12일 1월 130만원 6개월 기사") == set()


def test_best_family_signature_prefers_clean_product_name_over_noisy_text():
    service = ProductBlockingService()
    signature = service._best_family_signature(
        [
            "톤틴연금암치매12일눈길다양한보장130만원",
            "톤틴(Tontine) 연금",
        ],
        [],
    )

    assert signature == "톤틴연금"
    assert normalize_product_family_signature("건강보험부터 연금·종신보험까지 12일 130만원") != signature
