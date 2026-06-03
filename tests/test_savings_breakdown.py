from app.db.models import FactLLMCostLog
from app.services.llm_savings_service import LLMSavingsService


def test_savings_breakdown_helpers():
    service = LLMSavingsService()

    assert service.estimate_screening_savings(10, 4, 0.5) == 3.0
    assert service.estimate_cluster_savings(8, 3, 0.25) == 1.25
    assert service.estimate_selective_verification_savings(10, 2, 0.1) == 0.8


def test_cache_and_batch_savings():
    service = LLMSavingsService()
    cached = FactLLMCostLog(
        provider="gemini",
        model_name="default",
        task_type="extract",
        input_tokens=0,
        output_tokens=100,
        cached_tokens=500,
        estimated_cost_usd=0,
        batch_yn=False,
    )
    batch = FactLLMCostLog(
        provider="gemini",
        model_name="default",
        task_type="extract",
        input_tokens=1000,
        output_tokens=1000,
        cached_tokens=0,
        estimated_cost_usd=0.00025,
        batch_yn=True,
    )

    assert service.estimate_cache_savings([cached]) > 0
    assert service.estimate_batch_savings([batch]) > 0
