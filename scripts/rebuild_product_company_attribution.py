from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import DimCompany, DimProduct, FactArticle, FactProductArticle, FactProductObservation
from app.services.company_attribution_service import CompanyAttributionService


EXPORT_PATH = ROOT / "data" / "exports" / "product_company_attribution_plan.csv"


@dataclass(frozen=True)
class CompanyAttributionPlanRow:
    entity_type: str
    entity_id: int
    old_company: str | None
    new_company: str | None
    old_insurance_type: str | None
    new_insurance_type: str | None
    product_or_subject_name: str
    confidence: float
    reason: str
    article_url: str | None
    action: str


def build_product_company_attribution_plan(db: Session, *, limit: int | None = None) -> list[CompanyAttributionPlanRow]:
    service = CompanyAttributionService()
    query = db.query(DimProduct).filter(DimProduct.product_status != "merged").order_by(DimProduct.product_id.asc())
    if limit:
        query = query.limit(limit)
    rows: list[CompanyAttributionPlanRow] = []
    for product in query.all():
        context = _product_context(db, product)
        result = service.resolve_company_for_context(
            db,
            raw_company_name=product.company_name_raw,
            local_text=context["local_text"],
            previous_text=context["previous_text"],
            article_title=context["article_title"],
            article_description=context["article_description"],
            full_text=context["full_text"],
            expected_insurance_type=None,
            product_or_subject_name=product.normalized_product_name or product.raw_product_name,
        )
        old_company = _company_name(db, product.company_id) or product.company_name_raw
        changed = (result.company_id != product.company_id) or (
            bool(result.insurance_type)
            and result.insurance_type != product.insurance_type
            and product.insurance_type != "unknown"
        )
        if not changed and not result.needs_review:
            continue
        action = "review_company_attribution" if result.needs_review or not result.company_id else "update_company"
        rows.append(
            CompanyAttributionPlanRow(
                entity_type="product",
                entity_id=product.product_id,
                old_company=old_company,
                new_company=result.company_name_normalized,
                old_insurance_type=product.insurance_type,
                new_insurance_type=result.insurance_type,
                product_or_subject_name=product.normalized_product_name or product.raw_product_name,
                confidence=round(result.confidence, 4),
                reason=result.reason,
                article_url=context["article_url"],
                action=action,
            )
        )
    return rows


def apply_product_company_attribution_plan(db: Session, rows: list[CompanyAttributionPlanRow]) -> int:
    changed = 0
    for row in rows:
        product = db.get(DimProduct, row.entity_id)
        if not product:
            continue
        if row.action != "update_company" or not row.new_company:
            product.needs_review = True
            product.consolidation_status = "review"
            changed += 1
            continue
        company = _company_by_name(db, row.new_company)
        if not company:
            product.needs_review = True
            product.consolidation_status = "review"
            changed += 1
            continue
        product.company_id = company.company_id
        product.company_name_raw = company.company_name_normalized
        product.insurance_type = company.insurance_type_default or company.insurance_type or row.new_insurance_type or "unknown"
        _update_product_observations(db, product, company.company_name_normalized)
        changed += 1
    db.flush()
    return changed


def export_plan(rows: list[CompanyAttributionPlanRow], path: Path = EXPORT_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0]).keys()) if rows else list(CompanyAttributionPlanRow.__dataclass_fields__.keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))
    return path


def _product_context(db: Session, product: DimProduct) -> dict[str, str | None]:
    observations = (
        db.query(FactProductObservation)
        .filter(FactProductObservation.product_id == product.product_id)
        .order_by(FactProductObservation.observation_id.asc())
        .limit(20)
        .all()
    )
    article_ids = [item.article_id for item in observations if item.article_id]
    article_ids.extend(
        row[0]
        for row in db.query(FactProductArticle.article_id)
        .filter(FactProductArticle.product_id == product.product_id)
        .order_by(FactProductArticle.product_article_id.asc())
        .limit(20)
        .all()
    )
    seen_article_ids: list[int] = []
    for article_id in article_ids:
        if article_id and article_id not in seen_article_ids:
            seen_article_ids.append(article_id)
    articles = [db.get(FactArticle, article_id) for article_id in seen_article_ids[:20]]
    articles = [article for article in articles if article is not None]
    local_text = "\n".join(
        part
        for observation in observations
        for part in [observation.observation_context_text, observation.article_description]
        if part
    )
    local_text = "\n".join(
        part
        for part in [
            local_text,
            *[article.description for article in articles if article.description],
        ]
        if part
    )
    previous_text = "\n".join(item.article_title for item in observations if item.article_title)
    article_title = "\n".join(article.title for article in articles if article.title) or previous_text
    article_description = "\n".join(article.description for article in articles if article.description)
    full_text = "\n".join(
        part
        for part in [
            product.raw_product_name,
            product.normalized_product_name,
            product.company_name_raw,
            article_title,
            article_description,
            local_text,
        ]
        if part
    )
    return {
        "local_text": local_text,
        "previous_text": previous_text,
        "article_title": article_title,
        "article_description": article_description,
        "full_text": full_text,
        "article_url": (articles[0].original_url or articles[0].url) if articles else (observations[0].source_url if observations else None),
    }


def _company_name(db: Session, company_id: int | None) -> str | None:
    if company_id is None:
        return None
    company = db.get(DimCompany, company_id)
    return company.company_name_normalized if company else None


def _company_by_name(db: Session, company_name: str) -> DimCompany | None:
    return db.query(DimCompany).filter(DimCompany.company_name_normalized == company_name).first()


def _update_product_observations(db: Session, product: DimProduct, company_name: str) -> None:
    for observation in db.query(FactProductObservation).filter(FactProductObservation.product_id == product.product_id).all():
        observation.company_id = product.company_id
        observation.company_name_raw = company_name


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild product company attribution without LLM calls.")
    parser.add_argument("--apply", action="store_true", help="Apply safe company attribution updates. Defaults to dry-run.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output", type=Path, default=EXPORT_PATH)
    args = parser.parse_args()
    print("DB 백업 후 실행을 권장합니다. 기본은 dry-run이며 LLM/API 호출은 하지 않습니다.")
    with SessionLocal() as db:
        rows = build_product_company_attribution_plan(db, limit=args.limit)
        path = export_plan(rows, args.output)
        changed = apply_product_company_attribution_plan(db, rows) if args.apply else 0
        if args.apply:
            db.commit()
        print(f"plan_rows={len(rows)} changed={changed} csv={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
