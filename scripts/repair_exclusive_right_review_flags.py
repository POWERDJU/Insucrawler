from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

from sqlalchemy import func

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.database import SessionLocal
from app.db.models import FactExclusiveUseRight, FactExclusiveUseRightObservation
from app.normalizers.exclusive_right_subject_normalizer import is_allowed_canonical_exclusive_subject
from app.services.exclusive_right_consolidation_service import ExclusiveRightConsolidationService
from app.services.exclusive_right_local_context import has_bad_subject_tail, is_generic_or_weak_subject
from app.services.exclusive_right_local_context import is_valid_year_month


def _hard_review_ids(db) -> set[int]:
    service = ExclusiveRightConsolidationService()
    review_ids: set[int] = set()
    for block in service.blocking_service.build_blocks(db):
        if service._block_action(block.candidates) == "review":
            review_ids.update(candidate.exclusive_right_id for candidate in block.candidates)
    return review_ids


def _has_review_observation(db, exclusive_right_id: int) -> bool:
    return bool(
        db.query(func.count(FactExclusiveUseRightObservation.observation_id))
        .filter(
            FactExclusiveUseRightObservation.exclusive_right_id == exclusive_right_id,
            FactExclusiveUseRightObservation.needs_review.is_(True),
        )
        .scalar()
    )


def _safe_to_clear(row: FactExclusiveUseRight, hard_review_ids: set[int], has_review_observation: bool) -> bool:
    if row.event_status != "active" or not row.needs_review:
        return False
    if row.exclusive_right_id in hard_review_ids or has_review_observation:
        return False
    if row.company_id is None or not row.company_name_normalized:
        return False
    if row.exclusivity_months is None or int(row.exclusivity_months or 0) <= 0:
        return False
    if not is_valid_year_month(row.acquired_year_month):
        return False
    if (
        not is_allowed_canonical_exclusive_subject(row.subject_name)
        or is_generic_or_weak_subject(row.subject_name)
        or has_bad_subject_tail(row.subject_name)
    ):
        return False
    subject = " ".join(str(row.subject_name or "").split())
    compact = re.sub(r"[\s·ㆍ∙()\[\]{}'\"“”‘’/,-]", "", subject)
    if "..." in subject or len(subject) > 45 or len(compact) < 6:
        return False
    if any(fragment in subject for fragment in ("업계", "최초로", "호응", "체감형 혜택", "장기 손해 보험", "장기손해보험 최초")):
        return False
    if re.fullmatch(r"[가-힣A-Za-z0-9]{1,4}\s*보험", subject):
        return False
    if not re.search(r"(보험|특약|담보|서비스|제도|급부|검사|보장)", subject):
        return False
    return True


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    with SessionLocal() as db:
        before_visible = (
            db.query(func.count(FactExclusiveUseRight.exclusive_right_id))
            .filter(FactExclusiveUseRight.event_status == "active", FactExclusiveUseRight.needs_review.is_(False))
            .scalar()
        )
        hard_review_ids = _hard_review_ids(db)
        rows = (
            db.query(FactExclusiveUseRight)
            .filter(FactExclusiveUseRight.event_status == "active", FactExclusiveUseRight.needs_review.is_(True))
            .all()
        )
        clearable = [
            row
            for row in rows
            if _safe_to_clear(row, hard_review_ids, _has_review_observation(db, row.exclusive_right_id))
        ]
        if args.apply:
            for row in clearable:
                row.needs_review = False
            db.commit()
        after_visible = (
            db.query(func.count(FactExclusiveUseRight.exclusive_right_id))
            .filter(FactExclusiveUseRight.event_status == "active", FactExclusiveUseRight.needs_review.is_(False))
            .scalar()
        )
        print(
            {
                "mode": "apply" if args.apply else "dry_run",
                "active_visible_before": before_visible,
                "clearable_count": len(clearable),
                "active_visible_after": after_visible,
                "hard_review_candidate_count": len(hard_review_ids),
                "sample_clearable": [
                    {
                        "exclusive_right_id": row.exclusive_right_id,
                        "company": row.company_name_normalized,
                        "subject": row.subject_name,
                        "month": row.acquired_year_month,
                        "period": row.exclusivity_months,
                    }
                    for row in clearable[:20]
                ],
            }
        )


if __name__ == "__main__":
    main()
