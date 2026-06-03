from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import repository
from app.db.database import Base
from app.db.migrations import create_views
from app.db.models import DimCompany, DimProduct, FactArticle, FactExclusiveUseRight, FactLLMRun
from app.db.seed_master_data import seed_all
from app.services.company_attribution_service import CompanyAttributionService
from app.services.exclusive_right_service import ExclusiveRightService
from app.services.product_candidate_cluster_service import ProductCandidateClusterService
from app.services.screening_service import ScreeningService
from scripts.rebuild_exclusive_right_company_attribution import build_exclusive_right_company_attribution_plan


REPORT_PATH = ROOT / "docs" / "company-attribution-goal-result.md"


def main() -> int:
    results: dict[str, object] = {}
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "company_attribution_goal.db"
        engine = create_engine(f"sqlite:///{db_path}", future=True)
        SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
        Base.metadata.create_all(engine)
        create_views(engine)
        with SessionLocal() as db:
            seed_all(db)
            fixtures = _seed_goal_fixtures(db)
            results.update(_run_product_checks(db, fixtures))
            results.update(_run_cluster_checks(db))
            results.update(_run_exclusive_checks(db, fixtures))
            results.update(_run_short_alias_checks(db))
            results.update(_run_rebuild_checks(db, fixtures))
            results["article_level_same_product_llm_calls"] = (
                db.query(FactLLMRun)
                .filter(FactLLMRun.task_type.in_(["same_product_judge", "product_consolidation"]))
                .count()
            )
            results["total_llm_runs"] = db.query(FactLLMRun).count()
        engine.dispose()

    pass_fail = _evaluate(results)
    _write_report(results, pass_fail)
    print(json.dumps({"status": "PASS" if pass_fail else "FAIL", **results}, ensure_ascii=False, indent=2))
    return 0 if pass_fail else 1


def _seed_goal_fixtures(db) -> dict[str, int]:
    hanwha_life = _company(db, "한화생명")
    hanwha_general = _company(db, "한화손해보험")
    _company(db, "삼성생명")
    _company(db, "삼성화재")

    product_article = FactArticle(
        source_api="goal",
        title="한화생명 업계 신상품 소식",
        description="한화손해보험은 여성 고객 대상 시그니처 건강보험 4.0을 출시했다.",
        url="https://example.com/product-company-attribution",
        original_url="https://example.com/original/product-company-attribution",
        pub_date=datetime(2026, 1, 5, 9, 0, 0),
        content_hash="goal-product-company-attribution",
    )
    exclusive_article = FactArticle(
        source_api="goal",
        title="한화생명 보험업계 브리프",
        description="한화손해보험은 신규 담보로 손해보험협회 신상품심의위원회에서 6개월 배타적사용권을 획득했다.",
        url="https://example.com/exclusive-company-attribution",
        original_url="https://example.com/original/exclusive-company-attribution",
        pub_date=datetime(2026, 1, 6, 9, 0, 0),
        content_hash="goal-exclusive-company-attribution",
    )
    wrong_event = FactExclusiveUseRight(
        company_id=hanwha_life.company_id,
        company_name_normalized=hanwha_life.company_name_normalized,
        insurance_type=hanwha_life.insurance_type,
        subject_name="법률비용 지원 담보",
        subject_core_key="법률비용지원담보",
        exclusivity_months=6,
        acquired_year_month="2026-01",
        feature_summary="여성 고객 법률비용 지원 담보",
        evidence_text="한화손해보험은 법률비용 지원 담보로 손해보험협회 배타적사용권을 획득했다.",
        primary_article_title="한화생명 업계 브리프",
        primary_article_url="https://example.com/wrong-exclusive-company",
        article_count=1,
        confidence_total=0.8,
        needs_review=False,
        event_status="active",
    )
    db.add_all([product_article, exclusive_article, wrong_event])
    db.flush()
    return {
        "hanwha_general_id": hanwha_general.company_id,
        "product_article_id": product_article.article_id,
        "exclusive_article_id": exclusive_article.article_id,
        "wrong_event_id": wrong_event.exclusive_right_id,
    }


def _run_product_checks(db, fixtures: dict[str, int]) -> dict[str, int]:
    product = repository.upsert_product(
        db,
        {
            "raw_product_name": "시그니처 건강보험 4.0",
            "normalized_product_name": "시그니처 건강보험 4.0",
            "company_name": "한화생명",
            "insurance_type": "생명보험",
            "context_text": "한화손해보험은 여성 고객 대상 시그니처 건강보험 4.0을 출시했다.",
            "evidence_text": "한화손해보험은 여성 고객 대상 시그니처 건강보험 4.0을 출시했다.",
            "primary_product_type_code": "HEALTH_COMPREHENSIVE",
        },
    )
    db.flush()
    product_company_misattribution_count = 0
    if product is None or product.company_id != fixtures["hanwha_general_id"] or product.insurance_type != "손해보험":
        product_company_misattribution_count += 1
    return {"product_company_misattribution_count": product_company_misattribution_count}


def _run_cluster_checks(db) -> dict[str, int]:
    article = FactArticle(
        source_api="goal",
        title="삼성생명 업계 소식",
        description="삼성화재는 간편건강보험을 신규 출시했다.",
        url="https://example.com/cluster-company-attribution",
        original_url="https://example.com/original/cluster-company-attribution",
        pub_date=datetime(2026, 1, 7, 9, 0, 0),
        content_hash="goal-cluster-company-attribution",
    )
    db.add(article)
    db.flush()
    screening = ScreeningService().screen_article(db, article)
    cluster = ProductCandidateClusterService().upsert_for_article(db, article, screening, [])
    cluster_company_misattribution_count = 0
    if not cluster or cluster.candidate_company_name != "삼성화재":
        cluster_company_misattribution_count += 1
    return {"cluster_company_misattribution_count": cluster_company_misattribution_count}


def _run_exclusive_checks(db, fixtures: dict[str, int]) -> dict[str, int]:
    payload = {
        "exclusive_right_relevance": {
            "is_relevant": True,
            "status": "acquired",
            "reason": "획득 표현과 기간이 명시됨",
        },
        "exclusive_rights": [
            {
                "company_name_raw": "한화생명",
                "company_name_candidate": "한화생명",
                "subject": {
                    "raw_subject_name": "법률비용 지원 담보",
                    "normalized_subject_name_candidate": "법률비용 지원 담보",
                    "subject_core_key": "법률비용지원담보",
                },
                "exclusivity": {
                    "months": 6,
                    "evidence_text": "한화손해보험은 법률비용 지원 담보로 손해보험협회 배타적사용권을 획득했다.",
                },
                "acquired": {"year_month": "2026-01"},
                "feature_summary": "여성 고객 법률비용 지원 담보",
                "evidence_summary": "한화손해보험은 법률비용 지원 담보로 손해보험협회 배타적사용권을 획득했다.",
                "confidence": 0.9,
                "needs_review": False,
            }
        ],
    }
    ExclusiveRightService().save_extraction_result(db, fixtures["exclusive_article_id"], payload)
    db.flush()
    rows = (
        db.query(FactExclusiveUseRight)
        .filter(FactExclusiveUseRight.subject_core_key == "법률비용지원담보")
        .filter(FactExclusiveUseRight.primary_article_id == fixtures["exclusive_article_id"])
        .all()
    )
    exclusive_company_misattribution_count = sum(1 for row in rows if row.company_id != fixtures["hanwha_general_id"])
    return {"exclusive_company_misattribution_count": exclusive_company_misattribution_count}


def _run_short_alias_checks(db) -> dict[str, int]:
    result = CompanyAttributionService().resolve_company_for_context(
        db,
        raw_company_name="삼성",
        local_text="삼성은 보험 신상품을 소개했다.",
        product_or_subject_name="건강보험",
    )
    return {"short_alias_forced_match_count": 0 if result.company_id is None and result.needs_review else 1}


def _run_rebuild_checks(db, fixtures: dict[str, int]) -> dict[str, int]:
    rows = build_exclusive_right_company_attribution_plan(db)
    detected = any(
        row.entity_id == fixtures["wrong_event_id"]
        and row.action == "update_company"
        and row.new_company == "한화손해보험"
        for row in rows
    )
    return {"rebuild_candidates_detected": 1 if detected else 0}


def _company(db, name: str) -> DimCompany:
    company = db.query(DimCompany).filter(DimCompany.company_name_normalized == name).first()
    if not company:
        raise RuntimeError(f"required seeded company missing: {name}")
    return company


def _evaluate(results: dict[str, object]) -> bool:
    return (
        int(results.get("product_company_misattribution_count", 1)) == 0
        and int(results.get("cluster_company_misattribution_count", 1)) == 0
        and int(results.get("exclusive_company_misattribution_count", 1)) == 0
        and int(results.get("short_alias_forced_match_count", 1)) == 0
        and int(results.get("rebuild_candidates_detected", 0)) >= 1
        and int(results.get("article_level_same_product_llm_calls", 1)) == 0
        and int(results.get("total_llm_runs", 1)) == 0
    )


def _write_report(results: dict[str, object], passed: bool) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Company Attribution Goal Result",
        "",
        f"Status: {'PASS' if passed else 'FAIL'}",
        "",
        "This check uses a temporary SQLite database and does not call Naver, Gemini, Qwen, or any other external API.",
        "",
        "## Metrics",
        "",
    ]
    for key in sorted(results):
        lines.append(f"- `{key}`: {results[key]}")
    lines.extend(
        [
            "",
            "## Evidence",
            "",
            "- Product upsert resolves company from local product context before article title or raw LLM candidate.",
            "- Product candidate clusters pass title, description, and local launch text separately into the shared attribution service.",
            "- Exclusive-right extraction resolves company from the local exclusive-right evidence window and association hint.",
            "- Short aliases such as `삼성` do not force a company without stronger local evidence.",
            "- Rebuild dry-run detects an existing wrong exclusive-right company attribution candidate without LLM calls.",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
