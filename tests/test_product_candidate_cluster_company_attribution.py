from __future__ import annotations

from datetime import datetime

from app.db.models import FactArticle
from app.services.product_candidate_cluster_service import ProductCandidateClusterService
from app.services.screening_service import ScreeningService


def test_cluster_uses_local_product_window_company(db_session):
    article = FactArticle(
        source_api="test",
        title="삼성생명 업계 소식",
        description="삼성화재는 '간편건강보험'을 신규 출시했다.",
        url="https://example.com/cluster-company",
        original_url="https://example.com/original/cluster-company",
        pub_date=datetime(2026, 1, 5, 9, 0, 0),
        content_hash="cluster-company-attribution",
    )
    db_session.add(article)
    db_session.flush()

    screening = ScreeningService().screen_article(db_session, article)
    cluster = ProductCandidateClusterService().upsert_for_article(db_session, article, screening, [])

    assert cluster is not None
    assert cluster.candidate_company_name == "삼성화재"
