from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal


PREMIUM_HINTS = ("보험료", "월납", "월 보험료", "월초보험료", "초회보험료", "누적보험료")
COVERAGE_HINTS = ("보장", "보험금", "진단비", "수술비", "치료비", "입원비", "지원금", "비용", "가입금액")


@dataclass(frozen=True)
class AmountParseResult:
    amount_krw: int | None
    raw_text: str
    amount_type: str
    basis: str


def _korean_number_to_krw(num_text: str, unit_text: str) -> int:
    number = Decimal(num_text.replace(",", ""))
    total = Decimal(0)
    if "조" in unit_text:
        total += number * Decimal("1000000000000")
    elif "억" in unit_text:
        total += number * Decimal("100000000")
    elif "천만" in unit_text:
        total += number * Decimal("10000000")
    elif "백만" in unit_text:
        total += number * Decimal("1000000")
    elif "만" in unit_text:
        total += number * Decimal("10000")
    elif "천" in unit_text:
        total += number * Decimal("1000")
    else:
        total += number
    return int(total)


def parse_krw_amount(text: str | None) -> AmountParseResult:
    source = text or ""
    compact = source.replace(" ", "")
    amount_type = classify_amount_context(source)
    pattern = re.compile(r"(?P<num>\d+(?:,\d{3})*(?:\.\d+)?)(?P<unit>조원|억원|천만원|백만원|만원|원|조|억|천만|백만|만)?")
    match = pattern.search(compact)
    if not match:
        return AmountParseResult(None, source, amount_type, "amount_not_found")
    unit = match.group("unit") or "원"
    if unit in ("원",):
        amount = int(Decimal(match.group("num").replace(",", "")))
    else:
        amount = _korean_number_to_krw(match.group("num"), unit.replace("원", ""))
    return AmountParseResult(amount, match.group(0), amount_type, "deterministic_korean_unit")


def classify_amount_context(text: str | None) -> str:
    value = text or ""
    if any(hint in value for hint in PREMIUM_HINTS):
        if any(metric in value for metric in ("누적보험료", "월초보험료", "초회보험료", "판매실적")):
            return "sales_metric_amount"
        return "premium"
    if any(hint in value for hint in COVERAGE_HINTS):
        return "coverage_amount"
    return "unknown"


def normalize_coverage_amount(text: str | None) -> int | None:
    result = parse_krw_amount(text)
    if result.amount_type == "premium":
        return None
    return result.amount_krw if result.amount_type in {"coverage_amount", "unknown"} else None
