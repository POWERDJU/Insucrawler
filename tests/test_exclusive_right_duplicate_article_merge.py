from datetime import datetime

from app.db.models import FactArticle, FactExclusiveUseRight
from app.services.exclusive_right_consolidation_service import ExclusiveRightConsolidationService
from app.services.exclusive_right_service import ExclusiveRightService


def _article(db_session):
    article = FactArticle(
        source_api="naver",
        title="한화손해보험 배타적사용권 획득",
        description="한화손해보험은 OO보험에 대해 6개월 배타적사용권을 획득했다.",
        url="https://example.com/duplicate-exclusive",
        original_url="https://example.com/duplicate-exclusive",
        pub_date=datetime(2026, 1, 20),
        content_hash="duplicate-exclusive",
    )
    db_session.add(article)
    db_session.commit()
    return article


def test_duplicate_exclusive_article_aliases_are_preserved_on_merge(db_session):
    article = _article(db_session)
    service = ExclusiveRightService()
    canonical = service.upsert_observation(
        db_session,
        {"company_name_raw": "한화손해보험", "subject_name": "OO보험", "exclusivity_months": 6, "acquired_year_month": "2026-01", "confidence_total": 0.9},
        article=article,
        full_text=article.description,
    )
    duplicate = FactExclusiveUseRight(
        company_id=canonical.company_id,
        company_name_normalized=canonical.company_name_normalized,
        insurance_type=canonical.insurance_type,
        subject_name="OO 보험",
        subject_core_key="OO보험",
        exclusivity_months=6,
        acquired_year_month="2026-01",
        confidence_total=0.8,
        needs_review=False,
        event_status="active",
        alias_names_json='["OO 보험"]',
    )
    db_session.add(duplicate)
    db_session.commit()

    result = ExclusiveRightConsolidationService().run(db_session, mode="rule_only_apply")
    db_session.refresh(canonical)
    db_session.refresh(duplicate)

    assert result["auto_merge_count"] == 1
    assert duplicate.event_status == "merged"
    assert "OO 보험" in (canonical.alias_names_json or "")
