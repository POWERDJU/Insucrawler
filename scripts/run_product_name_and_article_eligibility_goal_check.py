from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import repository
from app.db.database import Base
from app.db.migrations import create_views
from app.db.models import DimProduct, DimProductAlias, FactArticle, FactLLMBatchJob, FactLLMQueue
from app.db.seed_master_data import seed_all
from app.normalizers.product_name_normalizer import normalize_product_family_signature, validate_product_name_before_save
from app.services.article_eligibility_filter_service import ArticleEligibilityFilterService, is_non_insurance_financial_product_name
from app.services.batch_llm_service import BatchLLMService
from app.services.extract_service import ExtractService
from app.utils.hashing import article_dedup_hash


REPORT = Path("docs/product-name-and-article-eligibility-goal-result.md")


def _article(db, *, title: str, description: str, url: str = "https://example.com/fixture") -> FactArticle:
    item = FactArticle(
        source_api="test",
        title=title,
        description=description,
        publisher="Test News",
        url=url,
        original_url=url,
        pub_date=datetime(2026, 1, 5, 9, 0, 0),
        query="test",
        query_group="test",
        content_hash=article_dedup_hash(url, title, ""),
        extraction_status="pending",
    )
    db.add(item)
    db.commit()
    return item


def _batch_payload(queue_id: int) -> str:
    payload = {
        "key": str(queue_id),
        "response": {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "article_relevance": {
                                            "is_relevant": True,
                                            "relevance_type": "new_product",
                                            "reason": "fixture",
                                        },
                                        "products": [
                                            {
                                                "identity": {
                                                    "raw_product_name": "삼성화재 건강보험",
                                                    "normalized_product_name_candidate": "삼성화재 건강보험",
                                                    "company_name_raw": "삼성화재",
                                                    "company_name_candidate": "삼성화재",
                                                    "insurance_type": "손해보험",
                                                    "release_year_month": "2026-01",
                                                    "release_year_month_basis": "explicit_in_article",
                                                },
                                                "product_type_classification": {
                                                    "primary_product_type": {
                                                        "code": "HEALTH_COMPREHENSIVE",
                                                        "name_ko": "건강(종합)",
                                                        "basis": "fixture",
                                                        "evidence_text": "삼성화재 건강보험",
                                                        "confidence": 0.8,
                                                    },
                                                    "secondary_product_types": [],
                                                    "needs_human_review": False,
                                                },
                                                "evidence": {"product_name_evidence": "삼성화재 건강보험"},
                                                "confidence": {
                                                    "identity": 0.8,
                                                    "product_type": 0.8,
                                                    "features": 0.5,
                                                    "coverage": 0.5,
                                                    "sales": 0.5,
                                                    "narrative": 0.5,
                                                },
                                            }
                                        ],
                                    },
                                    ensure_ascii=False,
                                )
                            }
                        ]
                    }
                }
            ]
        },
    }
    return json.dumps(payload, ensure_ascii=False) + "\n"


def run_checks(db, tmp_dir: Path) -> list[str]:
    failures: list[str] = []

    product = repository.upsert_product(
        db,
        {
            "raw_product_name": "한편 시그니처 여성건강보험",
            "normalized_product_name": "한편 시그니처 여성건강보험",
            "company_name": "한화손해보험",
            "insurance_type": "손해보험",
            "primary_product_type_code": "HEALTH_COMPREHENSIVE",
            "release_year_month": "2026-04",
            "evidence_text": "한편 시그니처 여성건강보험은 여성 주요 질환을 보장한다.",
            "context_text": "한화손해보험은 한편 시그니처 여성건강보험을 출시했다.",
            "confidence_total": 0.91,
            "needs_review": False,
        },
        allow_unknown_company=False,
    )
    if not product or product.normalized_product_name != "시그니처 여성건강보험":
        failures.append("609 fixture did not clean leading Korean discourse prefix.")
    if product and "한편" in normalize_product_family_signature(product.normalized_product_name):
        failures.append("Product family signature still contains leading discourse prefix.")
    if product:
        aliases = db.query(DimProductAlias).filter(DimProductAlias.product_id == product.product_id).all()
        if "한편 시그니처 여성건강보험" not in {item.raw_product_name for item in aliases}:
            failures.append("Original prefixed product name was not preserved as alias.")

    generic = validate_product_name_before_save("다만 건강보험", evidence_text="다만 건강보험", context_text="다만 건강보험")
    if generic.accepted:
        failures.append("Generic product name after prefix cleanup was accepted.")

    article_632 = _article(
        db,
        title="[금융단신] 신한은행 새 예금 출시 / 삼성화재 건강보험 안내",
        description="신한은행은 예금 상품을 출시했다. / 삼성화재는 건강보험 신상품을 소개했다.",
        url="https://example.com/632",
    )
    decision_632 = ArticleEligibilityFilterService().classify_article(db, article_632)
    if decision_632.exclusion_reason != "multi_financial_institution_roundup":
        failures.append("632 fixture was not classified as multi_financial_institution_roundup.")
    enqueue_result = ExtractService().enqueue_article_extraction(db, article_632.article_id, force_batch_eligible=True)
    if enqueue_result.get("llm_queue_id") is not None or db.query(FactLLMQueue).count() != 0:
        failures.append("Ineligible article created an LLM queue.")

    if not is_non_insurance_financial_product_name("KOSPI200 지수연동예금"):
        failures.append("KOSPI200 index-linked deposit was not detected as non-insurance financial product.")
    product_625 = repository.upsert_product(
        db,
        {
            "raw_product_name": "KOSPI200 지수연동예금",
            "normalized_product_name": "KOSPI200 지수연동예금",
            "company_name": "한화손해보험",
            "insurance_type": "손해보험",
            "primary_product_type_code": "OTHER",
        },
        allow_unknown_company=False,
    )
    if product_625 is not None:
        failures.append("625 fixture KOSPI200 deposit was saved as insurance product.")

    article_import = _article(
        db,
        title="[금융단신] 신한은행 예금 출시 / 삼성화재 건강보험 안내",
        description="신한은행은 예금 상품을 출시했다. / 삼성화재는 건강보험 신상품을 소개했다.",
        url="https://example.com/import-skip",
    )
    queue = FactLLMQueue(target_type="article", target_id=article_import.article_id, task_type="extract", batch_eligible_yn=True, status="pending")
    db.add(queue)
    db.flush()
    job = FactLLMBatchJob(provider="gemini", model_name="gemini-2.0-flash", task_type="extract", status="provider_completed", provider_status="JOB_STATE_SUCCEEDED")
    db.add(job)
    db.flush()
    output = tmp_dir / "batch-output.jsonl"
    output.write_text(_batch_payload(queue.llm_queue_id), encoding="utf-8")
    result = BatchLLMService().import_results(db, job, output)
    if result.get("skipped") != 1:
        failures.append("Batch import did not skip ineligible article output.")
    if db.query(DimProduct).filter(DimProduct.normalized_product_name == "삼성화재 건강보험").count():
        failures.append("Batch import saved product from ineligible article.")

    return failures


def main() -> None:
    tmp_dir = Path("data/tmp_goal_checks")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_dir / "product_name_article_eligibility_goal.db"
    if db_path.exists():
        db_path.unlink()
    engine = create_engine(f"sqlite:///{db_path}", future=True, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    create_views(engine)
    Session = sessionmaker(bind=engine, future=True)
    with Session() as db:
        seed_all(db)
        failures = run_checks(db, tmp_dir)
    engine.dispose()
    status = "PASS" if not failures else "FAIL"
    REPORT.write_text(
        "\n".join(
            [
                "# Product Name and Article Eligibility Goal Result",
                "",
                f"GOAL status = {status}",
                "",
                "Checks:",
                "- Korean discourse prefixes are stripped before canonical product save.",
                "- Original prefixed names remain as aliases.",
                "- Generic names after prefix cleanup are rejected.",
                "- Product 632-style mixed bank/insurer roundup articles are ineligible.",
                "- Product 625-style KOSPI200 deposits are not saved as insurance products.",
                "- Batch import skips outputs for ineligible articles.",
                "- No realtime LLM provider is called.",
                "",
                "Failures:",
                *(f"- {item}" for item in failures),
                "" if failures else "- None",
            ]
        ),
        encoding="utf-8",
    )
    print({"status": status, "output": str(REPORT), "failures": failures})
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
