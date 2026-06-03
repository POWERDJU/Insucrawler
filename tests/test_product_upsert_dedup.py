from app.db import repository
from app.db.models import DimProduct, DimProductAlias


def test_product_upsert_reuses_same_company_core_key_and_records_aliases(db_session):
    first = repository.upsert_product(
        db_session,
        {
            "raw_product_name": "한화손해보험 시그니처 여성건강 보험 4.0",
            "normalized_product_name": "한화손해보험 시그니처 여성건강 보험 4.0",
            "company_name": "한화손해보험",
            "insurance_type": "손해보험",
            "primary_product_type_code": "HEALTH_COMPREHENSIVE",
        },
    )
    second = repository.upsert_product(
        db_session,
        {
            "raw_product_name": "시그니처 여성건강보험 4.0",
            "normalized_product_name": "시그니처 여성건강보험 4.0",
            "company_name": "한화손보",
            "insurance_type": "손해보험",
            "primary_product_type_code": "HEALTH_COMPREHENSIVE",
        },
    )
    db_session.commit()

    assert second.product_id == first.product_id
    assert db_session.query(DimProduct).filter(DimProduct.company_id == first.company_id, DimProduct.product_core_key == first.product_core_key).count() == 1
    raw_names = {
        row.raw_product_name
        for row in db_session.query(DimProductAlias).filter(DimProductAlias.product_id == first.product_id).all()
    }
    assert "한화손해보험 시그니처 여성건강 보험 4.0" in raw_names
    assert "시그니처 여성건강보험 4.0" in raw_names


def test_product_upsert_reuses_samsung_new_simple_brain_heart_short_name(db_session):
    first = repository.upsert_product(
        db_session,
        {
            "raw_product_name": "삼성인터넷(신간편)뇌심건강보험",
            "normalized_product_name": "삼성인터넷(신간편)뇌심건강보험",
            "company_name": "삼성생명",
            "insurance_type": "생명보험",
            "primary_product_type_code": "HEALTH_COMPREHENSIVE",
        },
    )
    second = repository.upsert_product(
        db_session,
        {
            "raw_product_name": "뇌심 건강보험",
            "normalized_product_name": "뇌심 건강보험",
            "company_name": "삼성생명",
            "insurance_type": "생명보험",
            "primary_product_type_code": "HEALTH_COMPREHENSIVE",
        },
    )
    db_session.commit()

    assert second.product_id == first.product_id


def test_product_upsert_reuses_samsung_short_name_when_full_name_arrives_later(db_session):
    first = repository.upsert_product(
        db_session,
        {
            "raw_product_name": "뇌심 건강보험",
            "normalized_product_name": "뇌심 건강보험",
            "company_name": "삼성생명",
            "insurance_type": "생명보험",
            "primary_product_type_code": "HEALTH_COMPREHENSIVE",
        },
    )
    second = repository.upsert_product(
        db_session,
        {
            "raw_product_name": "삼성 인터넷 (신간편) 뇌심건강보험",
            "normalized_product_name": "삼성 인터넷 (신간편) 뇌심건강보험",
            "company_name": "삼성생명",
            "insurance_type": "생명보험",
            "primary_product_type_code": "HEALTH_COMPREHENSIVE",
        },
    )
    db_session.commit()

    assert second.product_id == first.product_id
    assert second.product_core_key == "신간편뇌심건강보험"
