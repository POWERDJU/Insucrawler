from app.db.models import FactArticle, FactContentScreening
from app.services.extract_service import ExtractService
from app.utils.hashing import sha256_text


class RaisingRouter:
    def run_pipeline(self, input_text, mode=None):
        raise AssertionError("LLM should not be called for irrelevant article")

    def run_extraction_only(self, input_text, mode=None):
        raise AssertionError("LLM should not be called for irrelevant article")

    def mode(self):
        return "gemini_only"

    def route_plan(self, mode=None):
        return {"extractor": {"provider": "gemini"}}


def test_irrelevant_article_is_screened_without_llm(db_session):
    article = FactArticle(
        source_api="naver",
        title="보험사 임직원 사회공헌 봉사활동",
        description="신상품이나 보장 내용과 무관한 행사 소식",
        url="https://example.com/irrelevant",
        original_url="https://example.com/irrelevant",
        content_hash=sha256_text("irrelevant"),
        extraction_status="pending",
    )
    db_session.add(article)
    db_session.commit()

    result = ExtractService(router=RaisingRouter()).extract_article(db_session, article.article_id)

    db_session.refresh(article)
    assert result["status"] == "screened_skip"
    assert article.extraction_status == "screened_skip"
    assert db_session.query(FactContentScreening).filter(FactContentScreening.article_id == article.article_id).count() == 1
