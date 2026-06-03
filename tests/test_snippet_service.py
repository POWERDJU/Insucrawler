from app.services.snippet_service import SnippetService


def test_snippet_service_extracts_launch_coverage_and_sales_sentences():
    text = (
        "한화손해보험은 새 건강보험을 신규 출시했다. "
        "해당 상품은 암 진단비와 수술비를 최대 1억원까지 보장한다. "
        "출시 한 달 만에 판매건수 1만건을 돌파했다."
    )

    snippets = SnippetService(context_sentences=0).extract_snippets(text)
    types = {snippet.snippet_type for snippet in snippets}

    assert {"launch", "coverage", "sales_metric"} <= types
    assert any("신규 출시" in snippet.snippet_text for snippet in snippets)


def test_snippet_bundle_uses_snippets_instead_of_full_text():
    service = SnippetService(context_sentences=0, max_chars=3000)
    snippets = service.extract_snippets("무관한 긴 본문. 삼성화재가 암보험을 출시했다. 진단비를 보장한다.")
    bundle = service.build_llm_input(
        title="삼성화재 암보험 출시",
        description="요약",
        source_type="naver",
        company_candidates=["삼성화재"],
        product_type_candidates=["CANCER"],
        snippets=snippets,
    )

    assert "snippets" in bundle
    assert "삼성화재" in bundle
