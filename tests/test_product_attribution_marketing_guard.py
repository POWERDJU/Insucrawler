from __future__ import annotations

from datetime import datetime

from app.db.models import DimCompany, FactArticle, FactArticleSnippet
from app.normalizers.company_normalizer import CompanyMatch
from app.services.multi_company_article_filter_service import MultiCompanyArticleFilterService
from app.services.product_company_eligibility import is_product_news_eligible_company
from app.services.product_attribution_guard_service import ProductAttributionGuardService
from app.services.product_candidate_cluster_service import ProductCandidateClusterService
from app.services.screening_service import ScreeningResult


def _article(db, *, title: str, description: str = "", suffix: str = "guard") -> FactArticle:
    article = FactArticle(
        source_api="test",
        title=title,
        description=description,
        url=f"https://example.com/{suffix}",
        content_hash=f"guard-{suffix}",
        pub_date=datetime(2026, 1, 1),
        extraction_status="pending",
    )
    db.add(article)
    db.flush()
    return article


def test_marketing_only_generic_product_is_observation_only(db_session):
    article = _article(
        db_session,
        title="현대해상, 간편건강보험 신규 TV 광고 공개",
        description="현대해상은 간편건강보험 신규 TV 광고 영상을 공개했다.",
        suffix="marketing-only",
    )

    result = ProductAttributionGuardService().validate_product_candidate(
        db_session,
        article=article,
        product_name="간편 건강보험",
        llm_company_candidate="한화손해보험",
        source_text="현대해상은 간편건강보험 신규 TV 광고 영상을 공개했다.",
        proposed_status="active",
    )

    assert result.create_product is False
    assert result.product_status == "rejected_marketing_only"
    assert result.marketing_only is True
    assert result.generic_product_name is True


def test_multi_company_filter_uses_saved_snippets(db_session):
    db_session.add_all(
        [
            DimCompany(company_name_normalized="Alpha손해보험", alias="Alpha손해보험", insurance_type="손해보험", company_role="nonlife_primary", include_in_product_news_default="Y"),
            DimCompany(company_name_normalized="Beta손해보험", alias="Beta손해보험", insurance_type="손해보험", company_role="nonlife_primary", include_in_product_news_default="Y"),
        ]
    )
    db_session.flush()

    class FakeNormalizer:
        def detect_all_with_positions(self, text):
            matches = []
            if "Alpha손해보험" in text:
                matches.append(
                    CompanyMatch(
                        company_name_raw="Alpha손해보험",
                        company_name_normalized="Alpha손해보험",
                        insurance_type="손해보험",
                        insurance_type_default="손해보험",
                        basis="test",
                        is_known_insurer=True,
                        confidence=0.95,
                        match_type="normalized",
                        needs_review=False,
                        company_role="nonlife_primary",
                        status_2024_2026="active",
                        include_in_product_news_default="Y",
                        notes=None,
                        start=text.index("Alpha손해보험"),
                        end=text.index("Alpha손해보험") + len("Alpha손해보험"),
                        alias_length=len("Alpha손해보험"),
                        is_short_alias=False,
                    )
                )
            if "Beta손해보험" in text:
                matches.append(
                    CompanyMatch(
                        company_name_raw="Beta손해보험",
                        company_name_normalized="Beta손해보험",
                        insurance_type="손해보험",
                        insurance_type_default="손해보험",
                        basis="test",
                        is_known_insurer=True,
                        confidence=0.95,
                        match_type="normalized",
                        needs_review=False,
                        company_role="nonlife_primary",
                        status_2024_2026="active",
                        include_in_product_news_default="Y",
                        notes=None,
                        start=text.index("Beta손해보험"),
                        end=text.index("Beta손해보험") + len("Beta손해보험"),
                        alias_length=len("Beta손해보험"),
                        is_short_alias=False,
                    )
                )
            return matches

    article = _article(
        db_session,
        title="Alpha손해보험 TV 광고 리뷰",
        description="Alpha손해보험 광고를 소개한다.",
        suffix="snippet-multi",
    )
    db_session.add(
        FactArticleSnippet(
            article_id=article.article_id,
            snippet_type="marketing",
            snippet_text="Beta손해보험 광고 캠페인도 함께 공개됐다.",
            sentence_index=1,
            matched_keywords_json="[]",
        )
    )
    db_session.flush()

    result = MultiCompanyArticleFilterService(normalizer=FakeNormalizer()).classify_article(db_session, article)

    assert result.is_multi_company is True
    assert set(result.company_names) == {"Alpha손해보험", "Beta손해보험"}


def test_cluster_company_candidates_are_not_final_company_when_no_local_evidence(db_session):
    screening = ScreeningResult(
        article_id=None,
        source_type="test",
        rule_relevance_score=0.9,
        matched_company_names=["?쒗솕?먰빐蹂댄뿕"],
        matched_product_type_codes=[],
        matched_launch_keywords=[],
        matched_negative_keywords=[],
        is_candidate=True,
        candidate_reason="company query hit",
        llm_required_yn=True,
        llm_priority="high",
    )

    company = ProductCandidateClusterService._detect_company(
        db_session,
        local_text="간편건강보험 광고 영상이 공개됐다.",
        article_title="간편건강보험 광고",
        article_description="회사명이 없는 광고 기사",
        full_text="간편건강보험 광고 영상이 공개됐다.",
        screening=screening,
        candidate_product_name="간편건강보험",
    )

    assert company is None


def test_ineligible_foreign_branch_is_not_product_company(db_session):
    db_session.add(
        DimCompany(
            company_name_normalized="Starr",
            alias="Starr|Star",
            insurance_type="손해보험",
            company_role="foreign_branch",
            include_in_product_news_default="N",
        )
    )
    db_session.flush()

    company = db_session.query(DimCompany).filter(DimCompany.company_name_normalized == "Starr").first()
    assert is_product_news_eligible_company(company) is False

    detected = ProductCandidateClusterService._detect_company(
        db_session,
        local_text="Starr has a small mention, but this is not an eligible product-news insurer.",
        article_title="Starr mention",
        article_description="Starr mention",
        full_text="Starr mention",
        screening=None,
        candidate_product_name="Travel insurance",
    )

    assert detected is None
