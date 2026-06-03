from datetime import datetime

from app.normalizers.date_normalizer import normalize_year_month


def test_explicit_korean_year_month():
    result = normalize_year_month("2026년 5월 출시")
    assert result.year_month == "2026-05"
    assert result.basis == "explicit_in_article"


def test_last_month_basis_from_article_date():
    result = normalize_year_month("지난달 출시했다", datetime(2026, 5, 26))
    assert result.year_month == "2026-04"
    assert result.basis == "inferred_from_article_date"


def test_unknown_date():
    result = normalize_year_month("출시 시점은 공개하지 않았다")
    assert result.year_month is None
    assert result.basis == "unknown"
