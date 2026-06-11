from app.services.monthly_new_product_service import MonthlyNewProductService


def test_monthly_summary_prefers_mobile_product_primary_summary():
    summary = MonthlyNewProductService()._summary(
        {
            "feature_summary": "abc xyz",
            "coverage_summary": "coverage text",
            "product_development_summary": "development text",
            "marketing_summary": "marketing text",
        },
        {"description": "article description", "title": "article title"},
    )

    assert summary == "abc xyz"
