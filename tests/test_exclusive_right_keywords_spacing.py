from app.services.screening_service import ScreeningService
from app.services.snippet_service import SnippetService


def test_spaced_exclusive_use_right_keywords_are_screened_and_snippeted():
    text = "한화손해보험은 신규 담보에 대해 6개월간의 배타적 사용권을 인정받았다."

    result = ScreeningService().screen_text(title=text, description="", body_text="")
    snippets = SnippetService().extract_snippets(text)

    assert result.exclusive_right_candidate_yn is True
    assert result.exclusive_right_score >= 0.70
    assert any(snippet.snippet_type == "exclusive_right" for snippet in snippets)


def test_spaced_exclusive_sales_right_keyword_is_treated_as_exclusive_candidate():
    text = "흥국생명은 신규 서비스에 대해 3개월 독점 사용권을 부여받았다."

    result = ScreeningService().screen_text(title=text, description="", body_text="")
    snippets = SnippetService().extract_snippets(text)

    assert result.exclusive_right_candidate_yn is True
    assert result.exclusive_right_score >= 0.70
    assert any(snippet.snippet_type == "exclusive_right" for snippet in snippets)
