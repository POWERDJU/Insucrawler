from app.db.models import FactExclusiveUseRight
from app.services.exclusive_right_consolidation_service import ExclusiveRightConsolidationService


def _event(db, *, company_id: int, company: str, subject: str, months: int, acquired: str = "2026-01"):
    row = FactExclusiveUseRight(
        company_id=company_id,
        company_name_normalized=company,
        insurance_type="생명보험" if "생명" in company or company in {"ABL생명", "삼성생명", "흥국생명"} else "손해보험",
        subject_name=subject,
        subject_core_key="".join(ch for ch in subject if ch.isalnum()),
        exclusivity_months=months,
        acquired_year_month=acquired,
        feature_summary=f"{subject} 배타적사용권",
        evidence_summary=f"{subject} {months}개월 배타적사용권 획득",
        evidence_text=f"{company}은 {subject}에 대해 {months}개월 배타적사용권을 획득했다.",
        article_count=1,
        confidence_total=0.9,
        needs_review=False,
        event_status="active",
    )
    db.add(row)
    db.flush()
    row.canonical_exclusive_right_id = row.exclusive_right_id
    return row


def test_actual_case_heungkuk_fire_target_dementia_mri_variants_merge(db_session):
    first = _event(db_session, company_id=1001, company="흥국화재", subject="표적치매 MRI검사비 특약", months=6)
    second = _event(db_session, company_id=1001, company="흥국화재", subject="표적치매치료 MRI 검사비용 보장 특약", months=6)
    third = _event(db_session, company_id=1001, company="흥국화재", subject="MRI 검사 지원비 보장 특약", months=6)
    db_session.commit()

    result = ExclusiveRightConsolidationService().run(db_session, mode="rule_only_apply")
    db_session.refresh(first)
    db_session.refresh(second)
    db_session.refresh(third)

    assert result["auto_merge_count"] >= 2
    assert sum(item.event_status == "active" for item in [first, second, third]) == 1
    canonical = next(item for item in [first, second, third] if item.event_status == "active")
    assert "MRI" in canonical.alias_names_json


def test_actual_case_abl_health_refund_variants_merge_and_weak_subject_not_canonical(db_session):
    first = _event(db_session, company_id=1002, company="ABL생명", subject="우리WON건강환급보험", months=9)
    second = _event(db_session, company_id=1002, company="ABL생명", subject="납입 특약보험료 건강환급금 지급", months=9)
    weak = _event(db_session, company_id=1002, company="ABL생명", subject="신상품", months=9)
    db_session.commit()

    result = ExclusiveRightConsolidationService().run(db_session, mode="rule_only_apply")
    db_session.refresh(first)
    db_session.refresh(second)
    db_session.refresh(weak)

    assert result["auto_merge_count"] >= 2
    canonical = next(item for item in [first, second, weak] if item.event_status == "active")
    assert canonical.subject_name != "신상품"
    assert "건강환급" in canonical.subject_name


def test_actual_case_kb_traditional_market_weather_variants_merge(db_session):
    first = _event(db_session, company_id=1003, company="KB손해보험", subject="KB전통시장 날씨피해 보상 보험", months=18, acquired="2025-11")
    second = _event(db_session, company_id=1003, company="KB손해보험", subject="전통시장 날씨 보험", months=18, acquired="2025-11")
    third = _event(db_session, company_id=1003, company="KB손해보험", subject="전통시장 날씨피해 보상 보험", months=18, acquired="2025-11")
    db_session.commit()

    result = ExclusiveRightConsolidationService().run(db_session, mode="rule_only_apply")
    db_session.refresh(first)
    db_session.refresh(second)
    db_session.refresh(third)

    assert result["auto_merge_count"] >= 2
    assert sum(item.event_status == "active" for item in [first, second, third]) == 1
    assert next(item for item in [first, second, third] if item.event_status == "active").acquired_year_month == "2025-11"


def test_actual_case_heungkuk_life_metastatic_cancer_advance_payment_variants_merge(db_session):
    first = _event(db_session, company_id=1004, company="흥국생명", subject="전이암진단시미리받는서비스 특약", months=6)
    second = _event(db_session, company_id=1004, company="흥국생명", subject="전이암 진단 시 미리 받는 서비스 특약", months=6)
    third = _event(db_session, company_id=1004, company="흥국생명", subject="전이암 및 중증 2대질병 진단 시 사망보험금 연금 선지급 특약", months=6)
    db_session.commit()

    result = ExclusiveRightConsolidationService().run(db_session, mode="rule_only_apply")
    db_session.refresh(first)
    db_session.refresh(second)
    db_session.refresh(third)

    assert result["auto_merge_count"] >= 2
    assert sum(item.event_status == "active" for item in [first, second, third]) == 1
    assert all(item.acquired_year_month != "2025-XX" for item in [first, second, third])
