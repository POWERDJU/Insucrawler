from app.llm.base import LLMResponse
from app.llm.qwen_provider import QwenProvider


class FakeQwenProvider(QwenProvider):
    def __init__(self):
        super().__init__(model_name="qwen-test", api_key="fake")
        self.calls = []

    def _chat_json(self, prompt: str, task_type: str) -> LLMResponse:
        self.calls.append({"prompt": prompt, "task_type": task_type})
        if task_type == "product_final_adjudication":
            output = {
                "decision": "accept",
                "canonical_product_name": "테스트보험",
                "company_name": "테스트손해보험",
                "release_year_month": "2026-05",
                "release_year_month_basis": "explicit_in_article",
                "partner_company_name": "테스트은행",
                "partner_role": "distribution_partner",
                "article_suitability": "product_launch_supported",
                "correction_summary": "release month corrected from local evidence",
                "reason": "supported",
                "evidence_quote": "2026년 5월 테스트보험을 출시했다.",
                "confidence": 0.9,
            }
        else:
            output = {
                "decision": "review",
                "subject_name": "테스트 배타적사용권",
                "company_name": "테스트손해보험",
                "acquired_year_month": "2026-05",
                "reason": "supported",
                "evidence_quote": "배타적사용권을 획득했다.",
                "confidence": 0.8,
            }
        return LLMResponse(
            provider="qwen",
            model_name=self.model_name,
            task_type=task_type,
            output_json=output,
            raw_text="{}",
        )


def test_qwen_product_final_adjudication_uses_extended_schema():
    provider = FakeQwenProvider()

    result = provider.adjudicate_product({"current_product_name": "테스트보험"})

    assert provider.calls[0]["task_type"] == "product_final_adjudication"
    assert "release_year_month" in provider.calls[0]["prompt"]
    assert "product-combination" in provider.calls[0]["prompt"]
    assert result["release_year_month"] == "2026-05"
    assert result["partner_company_name"] == "테스트은행"


def test_qwen_exclusive_final_adjudication_uses_dedicated_task_type():
    provider = FakeQwenProvider()

    result = provider.adjudicate_exclusive_right({"current_subject_name": "테스트 배타적사용권"})

    assert provider.calls[0]["task_type"] == "exclusive_right_final_adjudication"
    assert result["decision"] == "review"
