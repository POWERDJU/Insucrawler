from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.database import Base
from app.db.migrations import create_views
from app.db.models import DimCompany, DimProduct, FactLLMRun
from app.db.seed_master_data import seed_all
from app.services.dashboard_service import DashboardService
from app.services.product_consolidation_service import ProductConsolidationService
from app.services.product_duplicate_guard_service import ProductDuplicateGuardService
from app.services.product_full_list_consolidation_service import ProductFullListConsolidationService


TONTINE = "\ud1a4\ud2f4"
SIGNATURE = "\uc2dc\uadf8\ub2c8\ucc98"
HEALTH_REFUND = "\uac74\uac15\ud658\uae09"
REFUND = "\ud658\uae09"
SURGERY = "\uc804\uc2e0\ub9c8\ucde8\uc218\uc220"
STEPUP = "\uc2a4\ud15d\uc5c5700"
PET = "\ud3ab"
PET_BRAND = "\uae08\ucabd\uac19\uc740"


def _company(db, name: str, insurance_type: str = "\uc0dd\uba85\ubcf4\ud5d8") -> DimCompany:
    row = DimCompany(
        company_name_normalized=name,
        company_name_raw=name,
        alias=name,
        insurance_type=insurance_type,
        include_in_product_news_default="Y",
        active_yn="Y",
    )
    db.add(row)
    db.flush()
    return row


def _product(
    db,
    company: DimCompany,
    name: str,
    *,
    product_type: str = "HEALTH_COMPREHENSIVE",
    release_year_month: str = "2026-01",
    status: str = "active",
) -> DimProduct:
    row = DimProduct(
        raw_product_name=name,
        normalized_product_name=name,
        product_search_key=f"goal:{company.company_id}:{name}",
        product_core_key="".join(ch for ch in name.casefold() if ch.isalnum()),
        company_id=company.company_id,
        insurance_type=company.insurance_type,
        release_year_month=release_year_month,
        primary_product_type_code=product_type,
        product_status=status,
        confidence_total=0.9,
        needs_review=False,
    )
    db.add(row)
    db.flush()
    row.canonical_product_id = row.product_id
    return row


def _seed_goal_products(db) -> None:
    shinhan = _company(db, "\uc2e0\ud55c\ub77c\uc774\ud504\uc0dd\uba85")
    for name in [
        "\uc2e0\ud55c\ud1a4\ud2f4 \uc5f0\uae08\ubcf4\ud5d8",
        "\uc2e0\ud55c\ud1a4\ud2f4\uc5f0\uae08\ubcf4\ud5d8",
        "\ud1a4\ud2f4(Tontine) \uc5f0\uae08",
        "\ud55c\uad6d\ud615 \ud1a4\ud2f4\uc5f0\uae08\ubcf4\ud5d8",
        "\ud1a4\ud2f4\uc5f0\uae08\ubcf4\ud5d8",
        "\ud1a4\ud2f4 \uc5f0\uae08\ubcf4\ud5d8 \uc77c\ubd80\uc9c0\uae09\ud615",
        "\ud1a4\ud2f4 tontine \uc0c8 \uc5f0\uae08\ubcf4\ud5d8",
    ]:
        _product(db, shinhan, name, product_type="ANNUITY_SAVINGS")

    hanwha = _company(db, "\ud55c\ud654\uc190\ud574\ubcf4\ud5d8", insurance_type="\uc190\ud574\ubcf4\ud5d8")
    for name in [
        "\uc2dc\uadf8\ub2c8\ucc98 \uc5ec\uc131 \uac74\uac15\ubcf4\ud5d8 4.0",
        "\uc2dc\uadf8\ub2c8\ucc98 \uc5ec\uc131\ubcf4\ud5d8 4.0",
        "\ud55c\ud654 \uc2dc\uadf8\ub2c8\ucc98 \uc5ec\uc131 \uac74\uac15\ubcf4\ud5d8 4.0 \ubb34\ubc30\ub2f9",
        "\uc2dc\uadf8\ub2c8\ucc98 \uc5ec\uc131 \uac74\uac15 \ubcf4\ud5d8 4.0",
        "\ud55c\ud654\uc190\ud574\ubcf4\ud5d8 \uc2dc\uadf8\ub2c8\ucc98 \uc5ec\uc131\uac74\uac15\ubcf4\ud5d8 4.0",
    ]:
        _product(db, hanwha, name)
    _product(db, hanwha, "\uc2dc\uadf8\ub2c8\ucc98 \uc5ec\uc131\ubcf4\ud5d8 3.0")

    other = _company(db, "\ub2e4\ub978\uc190\ud574\ubcf4\ud5d8", insurance_type="\uc190\ud574\ubcf4\ud5d8")
    _product(db, other, "\uc2dc\uadf8\ub2c8\ucc98 \uc5ec\uc131\ubcf4\ud5d8 4.0")

    abl = _company(db, "ABL\uc0dd\uba85")
    for name in [
        "(\ubb34)\uc6b0\ub9acWON\uac74\uac15\ud658\uae09\ubcf4\ud5d8",
        "\uc6b0\ub9acWON\uac74\uac15\ud658\uae09\ubcf4\ud5d8",
        "\uac74\uac15\ud658\uae09\ubcf4\ud5d8",
        "\ubcf4\ud5d8\ub8cc \ud658\uae09\ud574\uc8fc\ub294 \uac74\uac15\ud658\uae09\ubcf4\ud5d8",
        "\ub0a9\uc785 \ud2b9\uc57d\ubcf4\ud5d8\ub8cc \ud658\uae09 \uc0c1\ud488",
        "\ud2b9\uc57d\ubcf4\ud5d8\ub8cc \ud658\uae09\ud615 \uac74\uac15\ubcf4\ud5d8",
        "\ud658\uae09\ubcf4\ud5d8",
    ]:
        _product(db, abl, name)
    _product(db, abl, "\uc6b0\ub9acWON\uc804\uc2e0\ub9c8\ucde8\uc218\uc220\ubcf4\ud5d8")
    _product(db, abl, "\uc804\uc2e0\ub9c8\ucde8\uc218\uc220\ubcf4\ud5d8")

    nh = _company(db, "NH\ub18d\ud611\uc0dd\uba85")
    _product(db, nh, "\uc2a4\ud15d\uc5c5700 \uc885\uc2e0\ubcf4\ud5d8", product_type="DEATH_WHOLELIFE")
    _product(db, nh, "\uc2a4\ud15d\uc5c5 700 NH \uc885\uc2e0\ubcf4\ud5d8", product_type="DEATH_WHOLELIFE", status="provisional")
    _product(db, nh, "\ud2b8\ub8e8\ub77c\uc774\ud504NH\uc885\uc2e0\ubcf4\ud5d8", product_type="DEATH_WHOLELIFE")

    kb = _company(db, "KB\uc190\ud574\ubcf4\ud5d8", insurance_type="\uc190\ud574\ubcf4\ud5d8")
    for index, name in enumerate([
        "KB \uae08\ucabd\uac19\uc740 \ud3ab\ubcf4\ud5d8",
        "\uae08\ucabd\uac19\uc740 \ud3ab\ubcf4\ud5d8",
        "\ud3ab\ubcf4\ud5d8",
        "KB \uae08\ucabd\uac19\uc740 \ud3ab \ubcf4\ud5d8 \uac1c\uc815",
    ]):
        _product(db, kb, name, product_type="PET", status="active" if index == 0 else "provisional")
    db.commit()


def _dashboard_request() -> dict[str, Any]:
    return {
        "include_review": True,
        "include_changed_companies": True,
        "include_short_term_insurers": True,
        "include_excluded_policy_products": True,
    }


def _row_counts(products: list[dict[str, Any]]) -> dict[str, int]:
    names = [str(item.get("normalized_product_name") or "") for item in products]
    hanwha = "\ud55c\ud654\uc190\ud574\ubcf4\ud5d8"
    other = "\ub2e4\ub978\uc190\ud574\ubcf4\ud5d8"
    return {
        "tontine": sum(1 for name in names if TONTINE in name),
        "signature_4_hanwha": sum(
            1
            for item in products
            if SIGNATURE in str(item.get("normalized_product_name") or "")
            and "4.0" in str(item.get("normalized_product_name") or "")
            and item.get("company_name") == hanwha
        ),
        "signature_4_other_company": sum(
            1
            for item in products
            if SIGNATURE in str(item.get("normalized_product_name") or "")
            and "4.0" in str(item.get("normalized_product_name") or "")
            and item.get("company_name") == other
        ),
        "signature_3": sum(1 for name in names if SIGNATURE in name and "3.0" in name),
        "health_refund": sum(1 for name in names if HEALTH_REFUND in name or REFUND in name),
        "surgery": sum(1 for name in names if SURGERY in name),
        "stepup_700": sum(1 for name in names if STEPUP in name or "\uc2a4\ud15d\uc5c5 700" in name),
        "pet_brand": sum(1 for name in names if PET_BRAND in name or "\ud3ab\ubcf4\ud5d8" in name),
    }


def _critical_group_count(groups: list[dict[str, Any]]) -> int:
    count = 0
    for group in groups:
        names = "\n".join(group.get("product_names") or [])
        if TONTINE in names or SIGNATURE in names or HEALTH_REFUND in names or REFUND in names:
            if SURGERY in names and (HEALTH_REFUND in names or REFUND in names):
                count += 1
            elif SURGERY not in names:
                count += 1
    return count


def _write_report(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# Product Consolidation GOAL Result",
        "",
        f"- GOAL: GOAL_PRODUCT_CONSOLIDATION_REAL_EXPORT_DUPLICATE_FIX_V2",
        f"- status: {result['status']}",
        f"- seeded_product_count: {result['seeded_product_count']}",
        f"- duplicate_groups_before: {result['duplicate_groups_before']}",
        f"- duplicate_groups_after_rule_only: {result['duplicate_groups_after_rule_only']}",
        f"- duplicate_groups_final: {result['duplicate_groups_final']}",
        f"- rule_only_auto_merge_count: {result['rule_only_auto_merge_count']}",
        f"- llm_assisted_status: {result['llm_assisted_status']}",
        f"- llm_run_count: {result['llm_run_count']}",
        f"- cached_run_count: {result['cached_run_count']}",
        "",
        "## Export Row Counts",
    ]
    for key, value in result["export_row_counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Assertions"])
    for assertion in result["assertions"]:
        lines.append(f"- {assertion}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    os.environ.setdefault("PRODUCT_CONSOLIDATION_LLM_ENABLED", "false")
    os.environ.setdefault("PRODUCT_LLM_CONSOLIDATION_ENABLED", "false")
    os.environ.setdefault("ENABLE_GEMINI_GROUNDING", "false")

    report_path = ROOT / "docs" / "product-consolidation-goal-result.md"
    assertions: list[str] = []
    with tempfile.TemporaryDirectory(prefix="product_goal_", ignore_cleanup_errors=True) as tmpdir:
        engine = create_engine(f"sqlite:///{Path(tmpdir) / 'goal.db'}", future=True, connect_args={"check_same_thread": False})
        try:
            Base.metadata.create_all(engine)
            create_views(engine)
            Session = sessionmaker(bind=engine, future=True)
            with Session() as db:
                seed_all(db)
                _seed_goal_products(db)
                seeded_count = db.query(DimProduct).count()

                guard = ProductDuplicateGuardService()
                before = guard.find_duplicate_family_groups(db)

                rule_result = ProductConsolidationService().run(db, mode="rule_only_apply", target="all", limit=0)
                after_rule = guard.find_duplicate_family_groups(db)

                llm_assisted_status = "not_needed"
                if _critical_group_count(after_rule):
                    os.environ["PRODUCT_LLM_CONSOLIDATION_ENABLED"] = "true"
                    llm_assisted_status = ProductFullListConsolidationService().run_full_list_consolidation(
                        db,
                        mode="dry_run",
                        target="all",
                        max_blocks=1,
                    ).get("status", "unknown")
                    os.environ["PRODUCT_LLM_CONSOLIDATION_ENABLED"] = "false"

                final_groups = guard.find_duplicate_family_groups(db)
                products = DashboardService()._products(db, _dashboard_request())
                counts = _row_counts(products)
                llm_run_count = db.query(FactLLMRun).count()
                cached_run_count = db.query(FactLLMRun).filter(FactLLMRun.cached_yn.is_(True)).count()

                checks = {
                    "tontine export row count == 1": counts["tontine"] == 1,
                    "Hanwha signature 4.0 export row count == 1": counts["signature_4_hanwha"] == 1,
                    "other company signature 4.0 remains separate": counts["signature_4_other_company"] == 1,
                    "signature 3.0 remains separate": counts["signature_3"] == 1,
                    "health refund export row count == 1": counts["health_refund"] == 1,
                    "whole body anesthesia surgery remains separate": counts["surgery"] == 1,
                    "real export row 46/138 StepUp 700 count == 1": counts["stepup_700"] == 1,
                    "real export row 115/116/117/120 pet product count == 1": counts["pet_brand"] == 1,
                    "critical duplicate groups cleared": _critical_group_count(final_groups) == 0,
                    "rule-only path did not call LLM": llm_run_count == 0,
                }
                assertions = [f"{'PASS' if ok else 'FAIL'}: {name}" for name, ok in checks.items()]
                status = "PASS" if all(checks.values()) else "FAIL"
                result = {
                    "status": status,
                    "seeded_product_count": seeded_count,
                    "duplicate_groups_before": len(before),
                    "duplicate_groups_after_rule_only": len(after_rule),
                    "duplicate_groups_final": len(final_groups),
                    "rule_only_auto_merge_count": rule_result.get("auto_merge_count", 0),
                    "llm_assisted_status": llm_assisted_status,
                    "llm_run_count": llm_run_count,
                    "cached_run_count": cached_run_count,
                    "export_row_counts": counts,
                    "assertions": assertions,
                }
                _write_report(report_path, result)
                print(f"{status}: wrote {report_path}")
                return 0 if status == "PASS" else 1
        finally:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
