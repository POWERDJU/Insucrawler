from app.llm.base import LLMProvider, LLMResponse
from app.llm.router import LLMRouter


class FakeProvider(LLMProvider):
    def __init__(self, provider_name):
        self.provider_name = provider_name

    def extract_product_info(self, input_text, schema, prompt_version):
        return LLMResponse(
            provider=self.provider_name,
            model_name="fake",
            task_type="extract",
            output_json={"article_relevance": {"is_relevant": True, "relevance_type": "new_product"}, "products": []},
            raw_text="{}",
        )

    def verify_extraction(self, input_text, extracted_json, schema, prompt_version):
        return LLMResponse(
            provider=self.provider_name,
            model_name="fake",
            task_type="verify",
            output_json={"verification_status": "pass", "field_checks": [], "overall_confidence": 0.9, "needs_human_review": False, "recommended_action": "save"},
            raw_text="{}",
        )

    def adjudicate_conflict(self, input_text, extraction_a, extraction_b, verification_result):
        return LLMResponse(provider=self.provider_name, model_name="fake", task_type="adjudicate", output_json={}, raw_text="{}")


def router():
    return LLMRouter(providers={"gemini:": FakeProvider("gemini"), "qwen:": FakeProvider("qwen")})


def test_gemini_extract_qwen_verify_routing():
    result = router().run_pipeline("text", "gemini_extract_qwen_verify")
    assert result["extractor"].provider == "gemini"
    assert result["verifier"].provider == "qwen"


def test_qwen_extract_gemini_verify_routing():
    result = router().run_pipeline("text", "qwen_extract_gemini_verify")
    assert result["extractor"].provider == "qwen"
    assert result["verifier"].provider == "gemini"


def test_qwen_first_cost_saver_conditional_verification():
    extraction = {
        "products": [
            {
                "identity": {"release_year_month": "2026-05"},
                "confidence": {"identity": 0.9},
                "major_coverages": [],
                "sales_metrics": [],
            }
        ]
    }
    assert LLMRouter.qwen_first_requires_verification(extraction) is True


def test_parallel_consensus_diff():
    result = router().run_pipeline("text", "parallel_consensus")
    assert result["extractor"].provider == "gemini"
    assert result["verifier"].provider == "qwen"
    assert result["diff"] == []
