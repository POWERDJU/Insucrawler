from app.db import repository
from app.services.crawl_job_service import CrawlJobService


MONTH_KEYWORDS = ("2026년 1월", "2026.01", "2026-01")


def query_texts(queries):
    return [item["query_text"] for item in queries]


def test_test_2026_01_query_generation_does_not_use_month_keyword(db_session):
    queries = CrawlJobService().generate_queries(
        db_session,
        year=2026,
        month=1,
        use_month_keyword=True,
        max_aliases_per_company=1,
        max_queries_per_company=12,
    )
    texts = query_texts(queries)

    assert "보험 신상품" in texts
    assert "보험 신상품 2026년 1월" not in texts
    assert any(text == "메리츠화재 신상품" for text in texts)
    assert not any(any(keyword in text for keyword in MONTH_KEYWORDS) for text in texts)
    assert any(item["company_name"] == "메리츠화재" for item in queries if item["query_group"] == "company")


def test_query_generation_limits_aliases_and_company_query_count_without_month_keyword(db_session):
    queries = CrawlJobService().generate_queries(
        db_session,
        year=2026,
        month=1,
        use_month_keyword=True,
        max_aliases_per_company=1,
        max_queries_per_company=2,
    )
    kb_queries = [item for item in queries if item.get("company_name") == "KB손해보험"]

    assert len(kb_queries) == 2
    assert all(not any(keyword in item["query_text"] for keyword in MONTH_KEYWORDS) for item in kb_queries)


def test_query_generation_excludes_reinsurers_by_default(db_session):
    default_queries = CrawlJobService().generate_queries(db_session, year=2026, month=1, max_queries_per_company=1)
    expanded_queries = CrawlJobService().generate_queries(db_session, year=2026, month=1, include_reinsurers=True, max_queries_per_company=1)

    assert not any(item.get("company_name") == "코리안리재보험" for item in default_queries)
    assert any(item.get("company_name") == "코리안리재보험" for item in expanded_queries)


def test_query_generation_includes_company_product_group_matrix(db_session):
    queries = CrawlJobService().generate_queries(db_session, year=2026, month=1, max_aliases_per_company=1, max_queries_per_company=80)
    texts = set(query_texts(queries))

    assert "삼성화재 건강보험" in texts
    assert "현대해상 운전자보험" in texts
    assert "마이브라운 펫보험" in texts
    assert "한화생명 종신보험" in texts
    assert "신한라이프생명 건강보험" in texts


def test_query_generation_uses_discovered_product_names_as_followup_queries(db_session):
    repository.upsert_product(
        db_session,
        {
            "raw_product_name": "여성 건강보험",
            "normalized_product_name": "여성 건강보험",
            "company_name": "한화손해보험",
            "insurance_type": "손해보험",
            "primary_product_type_code": "HEALTH_COMPREHENSIVE",
        },
    )
    repository.upsert_product(
        db_session,
        {
            "raw_product_name": "면역질환보험",
            "normalized_product_name": "면역질환보험",
            "company_name": "신한EZ손해보험",
            "insurance_type": "손해보험",
            "primary_product_type_code": "SPECIFIC_DISEASE",
        },
    )
    db_session.commit()

    queries = CrawlJobService().generate_queries(db_session, year=2026, month=1, max_aliases_per_company=0, max_queries_per_company=1)
    texts = set(query_texts(queries))

    assert "한화손해보험 여성 건강보험" in texts
    assert "신한EZ손해보험 면역질환보험" in texts
    assert not any(any(keyword in text for keyword in MONTH_KEYWORDS) for text in texts)
