from datetime import datetime

from app.db.models import FactArticle, FactArticleSnippet
from app.services.snippet_service import SnippetService


def test_exclusive_right_snippets_are_extracted_and_stored(db_session):
    article = FactArticle(
        source_api="naver",
        title="삼성화재 배타적사용권 획득",
        description="신상품심의위원회가 새로운 위험 담보에 6개월 배타적사용권을 부여했다.",
        url="https://example.com/exclusive-snippet",
        original_url="https://example.com/exclusive-snippet",
        pub_date=datetime(2026, 1, 10),
        content_hash="exclusive-snippet",
    )
    db_session.add(article)
    db_session.commit()

    snippets = SnippetService(context_sentences=0).extract_for_article(db_session, article)
    snippet_types = {snippet.snippet_type for snippet in snippets}
    stored_types = {row.snippet_type for row in db_session.query(FactArticleSnippet).filter_by(article_id=article.article_id).all()}

    assert "exclusive_right" in snippet_types
    assert "exclusive_period" in snippet_types
    assert "exclusive_feature" in snippet_types
    assert snippet_types <= stored_types
