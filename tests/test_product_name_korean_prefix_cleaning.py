from app.db import repository
from app.db.models import DimProductAlias
from app.normalizers.product_name_normalizer import (
    clean_product_name_candidate_result,
    normalize_product_family_signature,
    strip_korean_discourse_prefixes,
    validate_product_name_before_save,
)


def test_strip_korean_discourse_prefixes_removes_leading_only():
    cleaned, removed = strip_korean_discourse_prefixes("한편 시그니처 여성건강보험")
    assert cleaned == "시그니처 여성건강보험"
    assert removed == ["한편"]

    cleaned, removed = strip_korean_discourse_prefixes("한편 또한 시그니처 여성보험")
    assert cleaned == "시그니처 여성보험"
    assert removed == ["한편", "또한"]

    cleaned, removed = strip_korean_discourse_prefixes("시그니처 한편 여성건강보험")
    assert cleaned == "시그니처 한편 여성건강보험"
    assert removed == []


def test_product_name_cleaner_returns_removed_prefix_metadata():
    result = clean_product_name_candidate_result("아울러 우리WON건강환급보험")

    assert result.cleaned_name == "우리WON건강환급보험"
    assert result.removed_prefixes == ("아울러",)
    assert result.reject is False
    assert result.reason == "removed_leading_discourse_prefix"


def test_prefix_cleaned_generic_product_is_rejected():
    result = validate_product_name_before_save(
        "다만 건강보험",
        evidence_text="다만 건강보험 관련 보장을 설명했다.",
        context_text="다만 건강보험 관련 보장을 설명했다.",
    )

    assert result.accepted is False
    assert result.cleaned_name == "건강보험"
    assert result.reason in {"weak_or_generic_product_name", "bad_sentence_fragment"}


def test_repository_saves_canonical_without_discourse_prefix_and_keeps_alias(db_session):
    product = repository.upsert_product(
        db_session,
        {
            "raw_product_name": "한편 시그니처 여성건강보험",
            "normalized_product_name": "한편 시그니처 여성건강보험",
            "company_name": "한화손해보험",
            "insurance_type": "손해보험",
            "primary_product_type_code": "HEALTH_COMPREHENSIVE",
            "release_year_month": "2026-04",
            "evidence_text": "한편 시그니처 여성건강보험은 여성 주요 질환을 보장한다.",
            "context_text": "한화손해보험은 한편 시그니처 여성건강보험을 출시했다.",
            "confidence_total": 0.91,
            "needs_review": False,
        },
        allow_unknown_company=False,
    )

    assert product is not None
    assert product.normalized_product_name == "시그니처 여성건강보험"
    assert product.raw_product_name == "시그니처 여성건강보험"
    assert "한편" not in product.product_core_key
    assert "한편" not in normalize_product_family_signature(product.normalized_product_name)

    aliases = [
        alias.raw_product_name
        for alias in db_session.query(DimProductAlias).filter(DimProductAlias.product_id == product.product_id).all()
    ]
    assert "한편 시그니처 여성건강보험" in aliases


def test_generic_prefixed_name_does_not_create_active_product(db_session):
    product = repository.upsert_product(
        db_session,
        {
            "raw_product_name": "그러나 간편건강보험",
            "normalized_product_name": "그러나 간편건강보험",
            "company_name": "삼성화재",
            "insurance_type": "손해보험",
            "primary_product_type_code": "HEALTH_COMPREHENSIVE",
            "evidence_text": "그러나 간편건강보험 설명만 언급됐다.",
            "context_text": "그러나 간편건강보험 설명만 언급됐다.",
            "confidence_total": 0.7,
            "needs_review": False,
        },
        allow_unknown_company=False,
    )

    assert product is None
