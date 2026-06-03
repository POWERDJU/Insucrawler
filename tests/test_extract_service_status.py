from app.db.models import FactArticle
from app.llm.base import LLMResponse
from app.services.extract_service import ExtractService
from app.utils.hashing import sha256_text


class InvalidExtractionRouter:
    def run_pipeline(self, input_text, mode=None):
        return {
            "extractor": LLMResponse(
                provider="fake",
                model_name="fake",
                task_type="extract",
                output_json={"article_relevance": {"is_relevant": True, "relevance_type": "new_product"}, "products": "bad"},
                raw_text="{}",
            ),
            "verifier": None,
            "diff": [],
            "adjudicator": None,
        }


def test_extract_article_marks_schema_fail_article_status(db_session):
    article = FactArticle(
        source_api="unit",
        title="보험 신상품",
        description="schema fail",
        url="https://example.test/a",
        content_hash=sha256_text("https://example.test/a"),
        extraction_status="pending",
    )
    db_session.add(article)
    db_session.commit()

    result = ExtractService(router=InvalidExtractionRouter()).extract_article(db_session, article.article_id)
    db_session.refresh(article)

    assert result["status"] == "schema_fail"
    assert article.extraction_status == "schema_fail"
