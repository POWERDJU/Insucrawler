from app.db import repository
from app.normalizers.product_name_normalizer import product_core_key_candidates


def test_identity_rules_generate_tiered_keys_for_omitted_marketing_terms():
    keys = set(product_core_key_candidates("HI 시그니처 무배당 여성 건강보험 4.0", ["한화손해보험"]))

    assert "hi시그니처무배당여성건강보험4.0" in keys
    assert "hi시그니처여성건강보험4.0" in keys
    assert "시그니처여성건강보험4.0" in keys
    assert "여성건강보험4.0" in keys
    assert "여성4.0" in keys


def test_identity_rules_do_not_keep_too_generic_loose_keys():
    keys = set(product_core_key_candidates("시그니처 건강보험", []))

    assert "시그니처건강보험" in keys
    assert "건강보험" not in keys


def test_identity_rules_require_anchor_before_dropping_signature_prefix():
    broad_keys = set(product_core_key_candidates("시그니처 여성 건강보험", []))
    plain_keys = set(product_core_key_candidates("여성건강보험", []))
    versioned_keys = set(product_core_key_candidates("시그니처 여성 건강보험 4.0", []))
    short_versioned_keys = set(product_core_key_candidates("여성 4.0", []))

    assert "시그니처여성건강보험" in broad_keys
    assert not broad_keys.intersection(plain_keys)
    assert "여성4.0" in versioned_keys.intersection(short_versioned_keys)


def test_identity_rules_upsert_variants_to_same_company_product(db_session):
    first = repository.upsert_product(
        db_session,
        {
            "company_name": "한화손해보험",
            "insurance_type": "손해보험",
            "raw_product_name": "HI 시그니처 무배당 여성 건강보험 4.0",
            "normalized_product_name": "HI 시그니처 무배당 여성 건강보험 4.0",
            "primary_product_type_code": "HEALTH_COMPREHENSIVE",
        },
    )
    second = repository.upsert_product(
        db_session,
        {
            "company_name": "한화손해보험",
            "insurance_type": "손해보험",
            "raw_product_name": "여성 건강보험 4.0",
            "normalized_product_name": "여성 건강보험 4.0",
            "primary_product_type_code": "HEALTH_COMPREHENSIVE",
        },
    )
    third = repository.upsert_product(
        db_session,
        {
            "company_name": "한화손해보험",
            "insurance_type": "손해보험",
            "raw_product_name": "여성 4.0",
            "normalized_product_name": "여성 4.0",
            "primary_product_type_code": "HEALTH_COMPREHENSIVE",
        },
    )

    assert second.product_id == first.product_id
    assert third.product_id == first.product_id
