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
from app.db.models import (
    DimCompany,
    FactArticle,
    FactExclusiveUseRight,
    FactExclusiveUseRightArticle,
    FactExclusiveUseRightObservation,
)
from app.services.company_attribution_service import CompanyAttributionService


EXPORT_PATH = ROOT / "data" / "exports" / "exclusive_right_company_attribution_plan.csv"


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


def build_exclusive_right_company_attribution_plan(db: Session, *, limit: int | None = None) -> list[CompanyAttributionPlanRow]:
    service = CompanyAttributionService()
    query = (
        db.query(FactExclusiveUseRight)
        .filter(FactExclusiveUseRight.event_status != "merged")
        .filter(FactExclusiveUseRight.event_status != "rejected")
        .order_by(FactExclusiveUseRight.exclusive_right_id.asc())
    )
    if limit:
        query = query.limit(limit)
    rows: list[CompanyAttributionPlanRow] = []
    for event in query.all():
        context = _exclusive_context(db, event)
        result = service.resolve_company_for_context(
            db,
            raw_company_name=event.company_name_normalized,
            local_text=context["local_text"],
            previous_text=context["previous_text"],
            article_title=context["article_title"],
            article_description=context["article_description"],
            full_text=context["full_text"],
            association_hint=context["association_hint"],
            product_or_subject_name=event.subject_name,
        )
        old_company = _company_name(db, event.company_id) or event.company_name_normalized
        changed = (result.company_id != event.company_id) or (
            bool(result.insurance_type)
            and result.insurance_type != event.insurance_type
            and event.insurance_type != "unknown"
        )
        if not changed and not result.needs_review:
            continue
        action = "review_company_attribution" if result.needs_review or not result.company_id else "update_company"
        rows.append(
            CompanyAttributionPlanRow(
                entity_type="exclusive_right",
                entity_id=event.exclusive_right_id,
                old_company=old_company,
                new_company=result.company_name_normalized,
                old_insurance_type=event.insurance_type,
                new_insurance_type=result.insurance_type,
                product_or_subject_name=event.subject_name,
                confidence=round(result.confidence, 4),
                reason=result.reason,
                article_url=context["article_url"],
                action=action,
            )
        )
    return rows


def apply_exclusive_right_company_attribution_plan(db: Session, rows: list[CompanyAttributionPlanRow]) -> int:
    changed = 0
    for row in rows:
        event = db.get(FactExclusiveUseRight, row.entity_id)
        if not event:
            continue
        if row.action != "update_company" or not row.new_company:
            event.needs_review = True
            event.event_status = "review"
            changed += 1
            continue
        company = _company_by_name(db, row.new_company)
        if not company:
            event.needs_review = True
            event.event_status = "review"
            changed += 1
            continue
        insurance_type = company.insurance_type_default or company.insurance_type or row.new_insurance_type or "unknown"
        event.company_id = company.company_id
        event.company_name_normalized = company.company_name_normalized
        event.insurance_type = insurance_type
        for observation in (
            db.query(FactExclusiveUseRightObservation)
            .filter(FactExclusiveUseRightObservation.exclusive_right_id == event.exclusive_right_id)
            .all()
        ):
            observation.company_id = company.company_id
            observation.company_name_normalized = company.company_name_normalized
            observation.insurance_type = insurance_type
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


def _exclusive_context(db: Session, event: FactExclusiveUseRight) -> dict[str, str | None]:
    observation = (
        db.query(FactExclusiveUseRightObservation)
        .filter(FactExclusiveUseRightObservation.exclusive_right_id == event.exclusive_right_id)
        .order_by(FactExclusiveUseRightObservation.observation_id.asc())
        .first()
    )
    article = None
    if observation and observation.article_id:
        article = db.get(FactArticle, observation.article_id)
    if article is None and event.primary_article_id:
        article = db.get(FactArticle, event.primary_article_id)
    if article is None:
        link = (
            db.query(FactExclusiveUseRightArticle)
            .filter(FactExclusiveUseRightArticle.exclusive_right_id == event.exclusive_right_id)
            .order_by(FactExclusiveUseRightArticle.exclusive_right_article_id.asc())
            .first()
        )
        article = db.get(FactArticle, link.article_id) if link else None
    local_text = "\n".join(
        part
        for part in [
            observation.evidence_text if observation else None,
            event.evidence_text,
            event.evidence_summary,
            observation.feature_summary if observation else None,
        ]
        if part
    )
    article_title = (article.title if article else None) or event.primary_article_title or (observation.article_title if observation else None)
    article_description = article.description if article else None
    full_text = "\n".join(
        part
        for part in [
            event.subject_name,
            event.company_name_normalized,
            article_title,
            article_description,
            local_text,
        ]
        if part
    )
    return {
        "local_text": local_text,
        "previous_text": observation.article_title if observation else event.primary_article_title,
        "article_title": article_title,
        "article_description": article_description,
        "full_text": full_text,
        "association_hint": full_text,
        "article_url": (article.original_url or article.url) if article else event.primary_article_url,
    }


def _company_name(db: Session, company_id: int | None) -> str | None:
    if company_id is None:
        return None
    company = db.get(DimCompany, company_id)
    return company.company_name_normalized if company else None


def _company_by_name(db: Session, company_name: str) -> DimCompany | None:
    return db.query(DimCompany).filter(DimCompany.company_name_normalized == company_name).first()


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild exclusive-right company attribution without LLM calls.")
    parser.add_argument("--apply", action="store_true", help="Apply safe company attribution updates. Defaults to dry-run.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output", type=Path, default=EXPORT_PATH)
    args = parser.parse_args()
    print("DB 백업 후 실행을 권장합니다. 기본은 dry-run이며 LLM/API 호출은 하지 않습니다.")
    with SessionLocal() as db:
        rows = build_exclusive_right_company_attribution_plan(db, limit=args.limit)
        path = export_plan(rows, args.output)
        changed = apply_exclusive_right_company_attribution_plan(db, rows) if args.apply else 0
        if args.apply:
            db.commit()
        print(f"plan_rows={len(rows)} changed={changed} csv={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
