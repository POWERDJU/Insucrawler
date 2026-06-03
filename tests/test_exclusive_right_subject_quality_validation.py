from __future__ import annotations

from app.services.exclusive_right_local_context import (
    clean_exclusive_subject_candidate,
    has_bad_subject_tail,
    is_generic_or_weak_subject,
    validate_exclusive_subject_before_save,
)


def test_generic_subject_is_rejected_without_formal_reference():
    validation = validate_exclusive_subject_before_save(
        "상품",
        evidence_text="ABL생명은 상품에 대해 9개월 배타적사용권을 부여받았다.",
        window_text="ABL생명은 상품에 대해 9개월 배타적사용권을 부여받았다.",
        article_title="ABL생명 배타적사용권 획득",
    )

    assert validation.status == "rejected"
    assert validation.needs_review is True
    assert validation.subject_name is None


def test_generic_subject_resolves_to_formal_title_name():
    validation = validate_exclusive_subject_before_save(
        "상품",
        evidence_text="ABL생명은 상품에 대해 9개월 배타적사용권을 부여받았다.",
        window_text="ABL생명은 상품에 대해 9개월 배타적사용권을 부여받았다.",
        article_title="우리금융그룹 ABL생명, 납입한 특약보험료 건강환급금으로 돌려주는 '(무)우리WON건강환급보험' 배타적사용권 획득",
    )

    assert validation.status == "resolved"
    assert validation.subject_name in {"(무)우리WON건강환급보험", "우리WON건강환급보험"}
    assert validation.subject_name != "상품"


def test_bad_subject_tail_is_detected_and_cleaned():
    subject = "보장 특약을 개발해 손해 보험"

    assert has_bad_subject_tail(subject) is True
    assert is_generic_or_weak_subject("상품") is True
    assert "개발해" not in clean_exclusive_subject_candidate(subject)
