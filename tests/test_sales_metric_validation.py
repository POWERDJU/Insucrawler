from app.services.sales_metric_validation_service import SalesMetricValidationService


def test_sales_metric_requires_product_context():
    service = SalesMetricValidationService()

    decision = service.validate(
        {
            "metric_name": "매출",
            "metric_value": 3500,
            "metric_unit": "억원",
            "evidence_text": "상반기 연결 기준 매출은 3500억원을 기록했다.",
        },
        product_name="시그니처 여성건강보험",
        context_text="상반기 연결 기준 매출은 3500억원을 기록했다.",
    )

    assert decision.accepted is False
    assert decision.reason == "company_wide_metric_without_product_context"


def test_sales_metric_accepts_product_level_sentence():
    service = SalesMetricValidationService()

    decision = service.validate(
        {
            "metric_name": "판매건수",
            "metric_value": 12000,
            "metric_unit": "건",
            "evidence_text": "시그니처 여성건강보험은 출시 이후 판매건수 1만2000건을 넘었다.",
        },
        product_name="시그니처 여성건강보험",
        context_text="시그니처 여성건강보험은 출시 이후 판매건수 1만2000건을 넘었다.",
    )

    assert decision.accepted is True
