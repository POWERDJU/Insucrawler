from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.database import SessionLocal
from app.db.models import DimCompany, DimProduct, FactArticle, FactProductArticle, FactProductObservation
from app.services.company_attribution_service import CompanyAttributionService
from app.services.multi_company_article_filter_service import MultiCompanyArticleFilterService
from app.services.product_attribution_guard_service import ProductAttributionGuardService


def _company_name(db, company_id: int | None) -> str | None:
    if company_id is None:
        return None
    company = db.get(DimCompany, company_id)
    return company.company_name_normalized if company else None


def diagnose_product(db, product_id: int) -> dict:
    product = db.get(DimProduct, product_id)
    if not product:
        raise SystemExit(f"Product not found: {product_id}")
    articles = (
        db.query(FactArticle)
        .join(FactProductArticle, FactProductArticle.article_id == FactArticle.article_id)
        .filter(FactProductArticle.product_id == product_id)
        .order_by(FactArticle.article_id)
        .all()
    )
    observations = (
        db.query(FactProductObservation)
        .filter(FactProductObservation.product_id == product_id)
        .order_by(FactProductObservation.observation_id)
        .all()
    )
    guard = ProductAttributionGuardService()
    company_service = CompanyAttributionService()
    multi_service = MultiCompanyArticleFilterService()
    article_rows = []
    for article in articles:
        multi = multi_service.classify_article(db, article)
        local_window = guard.extract_product_local_window(
            article=article,
            product_name=product.normalized_product_name or product.raw_product_name,
            source_text="\n".join(obs.observation_context_text or "" for obs in observations if obs.article_id == article.article_id),
        )
        attribution = company_service.resolve_company_for_context(
            db,
            raw_company_name=product.company_name_raw,
            local_text=local_window,
            article_title=article.title,
            article_description=article.description,
            full_text="\n".join(part for part in [article.title, article.description, local_window] if part),
            product_or_subject_name=product.normalized_product_name or product.raw_product_name,
        )
        article_rows.append(
            {
                "article_id": article.article_id,
                "title": article.title,
                "url": article.original_url or article.url,
                "detected_companies": multi.company_names,
                "stored_multi_company": bool(article.multi_company_article_yn),
                "classified_multi_company": multi.is_multi_company,
                "local_resolved_company": attribution.company_name_normalized,
                "local_company_basis": attribution.basis,
                "company_conflict": bool(
                    attribution.company_name_normalized
                    and product.company_id
                    and attribution.company_name_normalized != _company_name(db, product.company_id)
                ),
                "marketing_only": guard.is_marketing_only_article(local_window),
                "local_window": local_window[:1000],
            }
        )
    return {
        "product_id": product.product_id,
        "product_name": product.normalized_product_name or product.raw_product_name,
        "current_company": _company_name(db, product.company_id),
        "company_name_raw": product.company_name_raw,
        "product_status": product.product_status,
        "needs_review": bool(product.needs_review),
        "source_article_count": len(articles),
        "observation_count": len(observations),
        "articles": article_rows,
    }


def render_markdown(report: dict) -> str:
    lines = [
        f"# Product Company Attribution Diagnosis: product_id={report['product_id']}",
        "",
        f"- product_name: {report['product_name']}",
        f"- current_company: {report['current_company']}",
        f"- company_name_raw: {report['company_name_raw']}",
        f"- product_status: {report['product_status']}",
        f"- needs_review: {report['needs_review']}",
        f"- source_article_count: {report['source_article_count']}",
        "",
        "## Article Evidence",
        "",
    ]
    for item in report["articles"]:
        lines.extend(
            [
                f"### article_id={item['article_id']}",
                f"- title: {item['title']}",
                f"- url: {item['url']}",
                f"- detected_companies: {', '.join(item['detected_companies'])}",
                f"- stored_multi_company: {item['stored_multi_company']}",
                f"- classified_multi_company: {item['classified_multi_company']}",
                f"- local_resolved_company: {item['local_resolved_company']} ({item['local_company_basis']})",
                f"- company_conflict: {item['company_conflict']}",
                f"- marketing_only: {item['marketing_only']}",
                "",
                "```text",
                item["local_window"],
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose product company attribution using deterministic local context.")
    parser.add_argument("--product-id", type=int, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    with SessionLocal() as db:
        report = diagnose_product(db, args.product_id)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render_markdown(report), encoding="utf-8")
        print(args.output)
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
