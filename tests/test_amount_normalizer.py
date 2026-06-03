from app.normalizers.amount_normalizer import classify_amount_context, normalize_coverage_amount, parse_krw_amount


def test_korean_amount_units():
    assert parse_krw_amount("암진단비 최대 1억원").amount_krw == 100_000_000
    assert parse_krw_amount("상해 수술비 5천만원").amount_krw == 50_000_000


def test_premium_is_not_coverage_amount():
    assert classify_amount_context("월 3만원대 보험료") == "premium"
    assert normalize_coverage_amount("월 3만원대 보험료") is None


def test_sales_metric_amount_context():
    result = parse_krw_amount("누적보험료 100억원을 기록했다")
    assert result.amount_krw == 10_000_000_000
    assert result.amount_type == "sales_metric_amount"


def test_max_coverage_and_premium_are_distinguished():
    assert normalize_coverage_amount("최대 보장금액 1억원") == 100_000_000
    assert normalize_coverage_amount("월 보험료 1만원") is None
