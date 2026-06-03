from app.db import repository
from app.db.models import DimProduct
from app.normalizers.product_name_normalizer import product_core_key_candidates


def test_hanwha_signature_woman_health_variants_share_fallback_key():
    aliases = ["한화손해보험", "한화손보", "한화화재"]
    short_keys = set(product_core_key_candidates("시그니처 여성 4.0", aliases))
    full_keys = set(product_core_key_candidates("시그니처 여성 건강보험 4.0", aliases))
    brand_full_keys = set(product_core_key_candidates("한화 시그니처 여성 건강보험 4.0", aliases))

    assert "시그니처여성4.0" in short_keys
    assert {"시그니처여성4.0", "여성4.0"}.issubset(short_keys.intersection(full_keys))
    assert {"시그니처여성4.0", "여성4.0"}.issubset(short_keys.intersection(brand_full_keys))


def test_hanwha_signature_woman_health_variants_upsert_to_same_product(db_session):
    first = repository.upsert_product(
        db_session,
        {
            "company_name": "한화손해보험",
            "insurance_type": "손해보험",
            "raw_product_name": "시그니처 여성 4.0",
            "normalized_product_name": "시그니처 여성 4.0",
            "primary_product_type_code": "HEALTH_COMPREHENSIVE",
        },
    )
    second = repository.upsert_product(
        db_session,
        {
            "company_name": "한화손해보험",
            "insurance_type": "손해보험",
            "raw_product_name": "한화 시그니처 여성 건강보험 4.0",
            "normalized_product_name": "한화 시그니처 여성 건강보험 4.0",
            "primary_product_type_code": "HEALTH_COMPREHENSIVE",
        },
    )

    assert second.product_id == first.product_id
    assert db_session.query(DimProduct).filter(DimProduct.company_id == first.company_id).count() == 1


def test_crew_screen_golf_variants_share_fallback_key():
    plain_keys = set(product_core_key_candidates("스크린골프보험", []))
    korean_brand_keys = set(product_core_key_candidates("크루 스크린골프보험", []))
    english_brand_keys = set(product_core_key_candidates("CREW 스크린골프보험", []))

    assert plain_keys == {"스크린골프보험"}
    assert plain_keys.intersection(korean_brand_keys) == {"스크린골프보험"}
    assert plain_keys.intersection(english_brand_keys) == {"스크린골프보험"}


def test_crew_screen_golf_variants_upsert_to_same_product(db_session):
    first = repository.upsert_product(
        db_session,
        {
            "company_name": "현대해상",
            "insurance_type": "손해보험",
            "raw_product_name": "크루 스크린골프보험",
            "normalized_product_name": "크루 스크린골프보험",
            "primary_product_type_code": "TRAVEL_LEISURE",
        },
    )
    second = repository.upsert_product(
        db_session,
        {
            "company_name": "현대해상",
            "insurance_type": "손해보험",
            "raw_product_name": "CREW 스크린골프보험",
            "normalized_product_name": "CREW 스크린골프보험",
            "primary_product_type_code": "TRAVEL_LEISURE",
        },
    )
    third = repository.upsert_product(
        db_session,
        {
            "company_name": "현대해상",
            "insurance_type": "손해보험",
            "raw_product_name": "스크린골프보험",
            "normalized_product_name": "스크린골프보험",
            "primary_product_type_code": "TRAVEL_LEISURE",
        },
    )

    assert second.product_id == first.product_id
    assert third.product_id == first.product_id
