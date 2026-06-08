from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.db.database import SessionLocal
from app.services.article_eligibility_filter_service import ArticleEligibilityFilterService
from app.services.monthly_new_product_service import MonthlyNewProductService
from app.services.product_type_industry_validation_service import ProductTypeIndustryValidationService


def main() -> None:
    failures: list[str] = []
    fixture = "[금융] IBK기업은행 KOSPI200 지수연동예금 출시 / 한화손보 야구장 스폰서데이 / 하나금융 지역아동 문화체험 / NH농협은행 에너지 절약 캠페인"
    with SessionLocal() as db:
        decision = ArticleEligibilityFilterService().classify_text(db, fixture)
        if decision.exclusion_reason != "multi_financial_institution_roundup":
            failures.append("KOSPI200 roundup fixture was not excluded as multi_financial_institution_roundup.")
        validation = ProductTypeIndustryValidationService().validate(insurance_type="손해보험", primary_product_type_code="DEATH_WHOLELIFE")
        if validation.valid:
            failures.append("Invalid nonlife + death product type was not rejected.")
        visible_kospi = db.execute(
            text("SELECT COUNT(*) FROM vw_product_search WHERE normalized_product_name LIKE '%KOSPI%' OR raw_product_name LIKE '%KOSPI%'")
        ).scalar()
        if visible_kospi:
            failures.append("KOSPI product remains visible in default product search view.")
        monthly = MonthlyNewProductService().get_monthly_new_products(db, fallback_latest=False)
        if "months" not in monthly or len(monthly["months"]) != 2:
            failures.append("Monthly board response does not expose current+previous months.")
        counts = {
            "dim_product": db.execute(text("SELECT COUNT(*) FROM dim_product")).scalar(),
            "visible_kospi": visible_kospi,
            "ineligible_articles": db.execute(text("SELECT COUNT(*) FROM fact_article WHERE COALESCE(multi_company_article_yn, 0) = 1")).scalar(),
            "invalid_industry_products": db.execute(text("SELECT COUNT(*) FROM dim_product WHERE product_status = 'excluded_invalid_industry_product_type'")).scalar(),
        }
    status = "PASS" if not failures else "FAIL"
    output = Path("docs/data-quality-cleanup-goal-result.md")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "\n".join(
            [
                "# Data Quality Cleanup Goal Result",
                "",
                f"Status: **{status}**",
                "",
                "## Checks",
                f"- KOSPI/multi-financial roundup exclusion: {decision.exclusion_reason}",
                f"- Invalid industry/product-type validation: {validation.exclusion_reason}",
                f"- Monthly board months: {monthly.get('months')}",
                f"- Counts: {counts}",
                "",
                "## Failures",
                *(f"- {item}" for item in failures),
            ]
        ),
        encoding="utf-8",
    )
    print({"status": status, "output": str(output), "failures": failures})
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
