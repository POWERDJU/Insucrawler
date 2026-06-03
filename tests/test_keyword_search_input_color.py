from __future__ import annotations


def test_keyword_search_inputs_have_visible_text_class():
    html = open("app/templates/dashboard.html", encoding="utf-8").read()

    for input_id in ["keywordInput", "mobileKeywordInput", "exclusiveRightKeyword", "mobileExclusiveKeyword"]:
        assert f'id="{input_id}" class="keyword-search"' in html


def test_keyword_search_input_text_color_is_black():
    css = open("app/static/dashboard.css", encoding="utf-8").read()

    assert "input.keyword-search" in css
    assert "color: #111111" in css
    assert "caret-color: #111111" in css
    assert "input.keyword-search::placeholder" in css
    assert "color: #666666" in css
