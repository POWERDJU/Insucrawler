from app.services.article_eligibility_filter_service import ArticleEligibilityFilterService
from app.services.product_name_validation_service import ProductNameValidationService


def test_senior_patient_descriptive_health_insurance_name_is_rejected():
    decision = ProductNameValidationService().validate(
        "\uace0\ub839\uc790 \uc720\ubcd1\uc790\ub97c \uc704\ud55c \uac74\uac15\ubcf4\ud5d8",
        evidence_text=(
            "\uace0\ub839\uc790\u00b7\uc720\ubcd1\uc790\ub97c \uc704\ud55c \uac74\uac15 \ubcf4\ud5d8\uacfc "
            "\uc554\u00b7\uac04\ubcd1 \ubcf4\ud5d8 \ub4f1 \uace0\uac1d \uc218\uc694\uc5d0 \ub9de\ucd98 \uc0c1\ud488\uc744 \ucd9c\uc2dc\ud588\ub2e4."
        ),
    )

    assert decision.accepted is False
    assert decision.reason == "weak_or_generic_product_name"


def test_big_three_life_insurer_earnings_roundup_is_excluded(db_session):
    decision = ArticleEligibilityFilterService().classify_text(
        db_session,
        (
            "\ube453 \uc0dd\ubcf4\uc0ac 1\ubd84\uae30 \uc6c3\uc5c8\ub2e4\u2026\uc0bc\uc804 \ub355\uc5d0 \uc720\ub3c5 \ube5b\ub09c \uc0bc\uc131\uc0dd\uba85\n"
            "\uac74\uac15\ubcf4\ud5d8\uc744 \ube44\ub86f\ud55c \ubcf4\uc7a5\uc131 \uc0c1\ud488 \ud310\ub9e4\ub97c \uc9c0\uc18d \ud655\ub300\ud558\uace0, "
            "\uace0\ub839\uc790\u00b7\uc720\ubcd1\uc790\ub97c \uc704\ud55c \uac74\uac15\ubcf4\ud5d8\uacfc \uace0\uac1d \uc218\uc694\uc5d0 \ub9de\ucd98 \uc0c1\ud488\uc744 \ucd9c\uc2dc\ud588\ub2e4."
        ),
    )

    assert decision.eligible_for_product_extraction is False
    assert decision.eligible_for_exclusive_right_extraction is False
    assert decision.exclusion_reason == "industry_trend_multi_company_article"
