from app.services.llm_queue_service import LLMQueueService
from app.services.screening_service import ScreeningService


def test_high_screening_can_create_extract_queue(db_session):
    screening = ScreeningService().screen_text(
        title="삼성화재 암보험 신상품 출시",
        description="암 진단비를 보장한다.",
        source_type="naver",
    )
    queue = None
    if screening.llm_required_yn:
        queue = LLMQueueService().enqueue(
            db_session,
            target_type="product_candidate_cluster",
            target_id=1,
            task_type="extract",
            priority=screening.llm_priority,
            batch_eligible_yn=True,
        )

    assert queue is not None
    assert queue.task_type == "extract"
    assert queue.priority == "high"


def test_low_screening_does_not_create_queue(db_session):
    screening = ScreeningService().screen_text(
        title="보험사 사회공헌 봉사활동",
        description="임직원 캠페인 소식",
        source_type="naver",
    )

    if screening.llm_required_yn:
        LLMQueueService().enqueue(db_session, target_type="article", target_id=1, task_type="extract")

    from app.db.models import FactLLMQueue

    assert db_session.query(FactLLMQueue).count() == 0


def test_risky_content_can_enqueue_verify(db_session):
    queue = LLMQueueService().enqueue(
        db_session,
        target_type="product",
        target_id=10,
        task_type="verify",
        priority="high",
        batch_eligible_yn=False,
    )

    assert queue.task_type == "verify"
