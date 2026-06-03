from datetime import datetime

from app.db.models import FactArticle
from app.services.product_candidate_cluster_service import ProductCandidateClusterService
from app.services.screening_service import ScreeningService
from app.services.snippet_service import SnippetService
from app.utils.hashing import sha256_text


def article(title, description, url):
    return FactArticle(
        source_api="naver",
        title=title,
        description=description,
        url=url,
        original_url=url,
        pub_date=datetime(2026, 1, 10),
        content_hash=sha256_text(url),
        extraction_status="pending",
    )


def test_same_company_and_core_key_articles_cluster_together(db_session):
    service = ProductCandidateClusterService()
    screening_service = ScreeningService()
    snippet_service = SnippetService(context_sentences=0)
    first = article("한화손해보험, 시그니처 여성 건강보험 4.0 출시", "'시그니처 여성 건강보험 4.0'을 신규 출시했다.", "https://a")
    second = article("한화손보 시그니처 여성 4.0 출시", "'시그니처 여성 4.0'을 선보였다.", "https://b")
    db_session.add_all([first, second])
    db_session.flush()

    c1 = service.upsert_for_article(db_session, first, screening_service.screen_article(db_session, first), snippet_service.extract_for_article(db_session, first))
    c2 = service.upsert_for_article(db_session, second, screening_service.screen_article(db_session, second), snippet_service.extract_for_article(db_session, second))

    assert c1.candidate_cluster_id == c2.candidate_cluster_id
    assert c1.article_count == 2


def test_same_core_key_different_company_does_not_cluster(db_session):
    service = ProductCandidateClusterService()
    screening_service = ScreeningService()
    first = article("삼성화재, 간편건강보험 출시", "'간편건강보험'을 신규 출시했다.", "https://c")
    second = article("한화손해보험, 간편건강보험 출시", "'간편건강보험'을 신규 출시했다.", "https://d")
    db_session.add_all([first, second])
    db_session.flush()

    c1 = service.upsert_for_article(db_session, first, screening_service.screen_article(db_session, first), [])
    c2 = service.upsert_for_article(db_session, second, screening_service.screen_article(db_session, second), [])

    assert c1.candidate_cluster_id != c2.candidate_cluster_id
