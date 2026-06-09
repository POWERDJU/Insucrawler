from __future__ import annotations

from app.services.exclusive_right_local_context import (
    has_bad_subject_tail,
    is_generic_or_weak_subject,
    validate_exclusive_subject_before_save,
)


def test_generic_subject_is_rejected_without_formal_reference():
    validation = validate_exclusive_subject_before_save(
        "\uc0c1\ud488",
        evidence_text="ABL\uc0dd\uba85\uc740 \uc0c1\ud488\uc5d0 \ub300\ud574 9\uac1c\uc6d4 \ubc30\ud0c0\uc801\uc0ac\uc6a9\uad8c\uc744 \ubd80\uc5ec\ubc1b\uc558\ub2e4.",
        window_text="ABL\uc0dd\uba85\uc740 \uc0c1\ud488\uc5d0 \ub300\ud574 9\uac1c\uc6d4 \ubc30\ud0c0\uc801\uc0ac\uc6a9\uad8c\uc744 \ubd80\uc5ec\ubc1b\uc558\ub2e4.",
        article_title="ABL\uc0dd\uba85 \ubc30\ud0c0\uc801\uc0ac\uc6a9\uad8c \ud68d\ub4dd",
    )

    assert validation.status == "rejected"
    assert validation.needs_review is True
    assert validation.subject_name is None


def test_generic_subject_resolves_to_formal_title_name():
    evidence = (
        "DB\uc190\ud574\ubcf4\ud5d8\uc758 '\ubcf4\ud589\uc790\uc0ac\uace0 "
        "\ubcc0\ud638\uc0ac\uc790\ubb38\ube44\uc6a9 \uc9c0\uc6d0 \ud2b9\ubcc4\uc57d\uad00'\uc774 "
        "3\uac1c\uc6d4\uc758 \ubc30\ud0c0\uc801\uc0ac\uc6a9\uad8c\uc744 \ubc1b\uc558\ub2e4."
    )
    validation = validate_exclusive_subject_before_save(
        "\uc0c1\ud488",
        evidence_text=evidence,
        window_text=evidence,
        article_title=(
            "DB\uc190\ud574\ubcf4\ud5d8, '\ubcf4\ud589\uc790\uc0ac\uace0 "
            "\ubcc0\ud638\uc0ac\uc790\ubb38\ube44\uc6a9 \uc9c0\uc6d0 \ud2b9\ubcc4\uc57d\uad00' "
            "\ubc30\ud0c0\uc801\uc0ac\uc6a9\uad8c \ud68d\ub4dd"
        ),
    )

    assert validation.status == "resolved"
    assert validation.subject_name == "\ubcf4\ud589\uc790\uc0ac\uace0 \ubcc0\ud638\uc0ac\uc790\ubb38\ube44\uc6a9 \uc9c0\uc6d0 \ud2b9\ubcc4\uc57d\uad00"
    assert validation.needs_review is False


def test_bad_subject_tail_is_detected():
    subject = "\ubcf4\uc7a5 \ud2b9\uc57d\uc744 \uac1c\ubc1c\ud55c \ubcf4\ud5d8"

    assert has_bad_subject_tail(subject) is True
    assert is_generic_or_weak_subject("\uc0c1\ud488") is True


def test_exclusive_right_system_description_is_rejected():
    subject = "\uc720\uc6a9\uc131 \ub4f1\uc744 \ud3c9\uac00\ud574 \ucd5c\ub300 1\ub144\uac04 \ub3c5\uc810 \ud310\ub9e4 \uad8c\ub9ac\ub97c \ubd80\uc5ec\ud558\ub294 \uc81c\ub3c4"
    evidence = (
        "\ubc30\ud0c0\uc801\uc0ac\uc6a9\uad8c\uc740 \uc2e0\uc0c1\ud488\uc2ec\uc758\uc704\uc6d0\ud68c\uac00 "
        "\ub3c5\ucc3d\uc131, \uc9c4\ubcf4\uc131, \uc720\uc6a9\uc131 \ub4f1\uc744 \ud3c9\uac00\ud574 "
        "\ucd5c\ub300 1\ub144\uac04 \ub3c5\uc810 \ud310\ub9e4 \uad8c\ub9ac\ub97c \ubd80\uc5ec\ud558\ub294 \uc81c\ub3c4\ub2e4."
    )

    validation = validate_exclusive_subject_before_save(
        subject,
        evidence_text=evidence,
        window_text=evidence,
        article_title="DB\uc190\ud574\ubcf4\ud5d8 \ud3ab\ubcf4\ud5d8 \ubc30\ud0c0\uc801\uc0ac\uc6a9\uad8c \ud604\ud669",
    )

    assert is_generic_or_weak_subject(subject) is True
    assert has_bad_subject_tail(subject) is True
    assert validation.status == "rejected"
    assert validation.needs_review is True
    assert validation.subject_name is None
