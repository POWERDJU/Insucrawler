from sqlalchemy import text


NEW_CODES = [
    "SPECIFIC_DISEASE",
    "MEDICAL_INDEMNITY",
    "AUTO",
    "TRAVEL_LEISURE",
    "PET",
    "DENTAL",
    "ANNUITY_SAVINGS",
    "VARIABLE_UL",
    "GUARANTEE_CREDIT",
    "CORPORATE_GROUP_SPECIALTY",
]


EXPECTED_ORDER = [
    "DEATH_WHOLELIFE",
    "HEALTH_COMPREHENSIVE",
    "SPECIFIC_DISEASE",
    "CANCER",
    "MEDICAL_INDEMNITY",
    "ACCIDENT_DRIVER",
    "AUTO",
    "SIMPLIFIED_IMPAIRED",
    "DEMENTIA_CARE",
    "CHILD_ADULT_CHILD",
    "DENTAL",
    "PET",
    "TRAVEL_LEISURE",
    "PROPERTY_EXPENSE",
    "GUARANTEE_CREDIT",
    "ANNUITY_SAVINGS",
    "VARIABLE_UL",
    "CORPORATE_GROUP_SPECIALTY",
    "OTHER",
    "UNKNOWN",
]


def test_product_type_master_contains_expanded_market_taxonomy(db_session):
    rows = db_session.execute(
        text(
            """
            SELECT product_type_code, product_type_name_ko, sort_order
            FROM dim_product_type
            WHERE active_yn = 'Y'
            ORDER BY sort_order
            """
        )
    ).mappings().all()
    codes = [row["product_type_code"] for row in rows]
    names = {row["product_type_code"]: row["product_type_name_ko"] for row in rows}

    for code in NEW_CODES:
        assert code in codes
    assert names["DEATH_WHOLELIFE"] == "사망(종신/정기)"
    assert codes == EXPECTED_ORDER
