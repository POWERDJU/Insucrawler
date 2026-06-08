from __future__ import annotations

from datetime import datetime

from app.db.models import DimProduct, FactArticle, FactExclusiveUseRight, FactExclusiveUseRightArticle, FactProductArticle, FactQwenReviewAudit
from app.normalizers.product_name_normalizer import product_search_key
from app.services.article_eligibility_filter_service import ArticleEligibilityFilterService
from app.services.exclusive_right_local_context import validate_exclusive_subject_before_save
from app.services.product_name_validation_service import ProductNameValidationService
from app.services.qwen_quality_review_service import (
    QWEN_EXCLUSIVE_RIGHT_QUALITY_REVIEW_TASK_TYPE,
    QWEN_PRODUCT_QUALITY_REVIEW_TASK_TYPE,
    QwenQualityReviewRequest,
    QwenQualityReviewService,
)
from app.services.product_final_adjudication_service import (
    ProductFinalAdjudicationDecision,
    ProductFinalAdjudicationInput,
    ProductFinalAdjudicationService,
)
from app.services.exclusive_right_final_adjudication_service import (
    ExclusiveRightFinalAdjudicationDecision,
    ExclusiveRightFinalAdjudicationInput,
    ExclusiveRightFinalAdjudicationService,
)
from app.utils.hashing import article_dedup_hash


class FakeQwenQualityProvider:
    def __init__(self) -> None:
        self.product_calls = 0
        self.exclusive_calls = 0

    def adjudicate_product(self, payload):
        self.product_calls += 1
        return {
            "decision": "accept",
            "canonical_product_name": payload["current_product_name"],
            "company_name": payload.get("current_company") or "한화손해보험",
            "release_year_month": payload.get("current_release_year_month") or "2025-03",
            "release_year_month_basis": "explicit_in_article",
            "reason": "fake full quality review",
            "evidence_quote": "한화손해보험은 테스트보험을 출시했다.",
            "confidence": 0.91,
        }

    def adjudicate_exclusive_right(self, payload):
        self.exclusive_calls += 1
        return {
            "decision": "accept",
            "subject_name": payload["current_subject_name"],
            "company_name": payload.get("current_company") or "한화손해보험",
            "acquired_year_month": payload.get("acquired_year_month") or "2025-03",
            "reason": "fake full quality review",
            "evidence_quote": "테스트 특약은 배타적사용권을 획득했다.",
            "confidence": 0.9,
        }


def test_quality_error_patterns_are_blocked_by_rules(db_session):
    assert ProductNameValidationService().validate("따라보험").accepted is False
    assert ProductNameValidationService().validate("계리가정에보험").accepted is False

    subject = validate_exclusive_subject_before_save(
        "보험 특허 상품",
        evidence_text="보험 특허 상품이라고 표현했다.",
        window_text="보험 특허 상품이라고 표현했다.",
    )
    assert subject.needs_review is True

    subject = validate_exclusive_subject_before_save(
        "CNB뉴스 위클리픽- 보험",
        evidence_text="CNB뉴스 위클리픽- 보험",
        window_text="CNB뉴스 위클리픽- 보험",
    )
    assert subject.needs_review is True


def test_financial_roundup_and_market_articles_are_ineligible(db_session):
    service = ArticleEligibilityFilterService()

    loan = service.classify_text(
        db_session,
        "IBK기업은행, i-ONE 징검다리론 출시\n한화손해보험 소식도 함께 전했다.",
    )
    assert loan.is_eligible is False
    assert loan.exclusion_reason in {"non_insurance_financial_product", "multi_financial_institution_roundup"}

    roundup = service.classify_text(
        db_session,
        "[금융 이모저모] 우리금융 새 서비스 / 한화손해보험, 내삶엔 3N 맞춤간편건강보험 출시",
    )
    assert roundup.is_eligible is False
    assert roundup.exclusion_reason == "multi_financial_institution_roundup"

    market = service.classify_text(
        db_session,
        "4월 新계리가정에 보험사 일제히 상품 새 단장 출시",
    )
    assert market.is_eligible is False
    assert market.exclusion_reason == "industry_trend_multi_company_article"


def test_qwen_quality_review_uses_separate_audit_task_types(db_session, tmp_path):
    article = FactArticle(
        source_api="test",
        title="한화손해보험, 테스트보험 출시",
        description="한화손해보험은 테스트보험을 출시하고 테스트 특약 배타적사용권을 획득했다.",
        publisher="test",
        url="https://example.com/qwen-quality",
        original_url="https://example.com/qwen-quality",
        pub_date=datetime(2025, 3, 1),
        query="test",
        query_group="test",
        content_hash=article_dedup_hash("https://example.com/qwen-quality", "한화손해보험, 테스트보험 출시", ""),
    )
    db_session.add(article)
    db_session.flush()
    product = DimProduct(
        normalized_product_name="테스트보험",
        raw_product_name="테스트보험",
        company_name_raw="한화손해보험",
        product_search_key=product_search_key("테스트보험", "한화손해보험"),
        release_year_month="2025-03",
        release_year_month_basis="explicit_in_article",
        needs_review=False,
        product_status="active",
    )
    db_session.add(product)
    db_session.flush()
    exclusive = FactExclusiveUseRight(
        subject_name="테스트 특약",
        company_name_normalized="한화손해보험",
        acquired_year_month="2025-03",
        evidence_text="테스트 특약은 배타적사용권을 획득했다.",
        needs_review=False,
        event_status="active",
    )
    db_session.add(exclusive)
    db_session.flush()
    db_session.add(FactProductArticle(product_id=product.product_id, article_id=article.article_id))
    db_session.add(FactExclusiveUseRightArticle(exclusive_right_id=exclusive.exclusive_right_id, article_id=article.article_id))
    db_session.commit()

    provider = FakeQwenQualityProvider()
    summary = QwenQualityReviewService(provider=provider).run(
        db_session,
        QwenQualityReviewRequest(
            mode="dry_run",
            date_from="2025-03-01",
            date_to="2025-03-31",
            require_live_qwen=True,
            output_dir=tmp_path,
            report_path=tmp_path / "quality-review.md",
        ),
    )

    assert summary["status"] == "completed"
    assert provider.product_calls == 1
    assert provider.exclusive_calls == 1
    task_types = {row.task_type for row in db_session.query(FactQwenReviewAudit).all()}
    assert QWEN_PRODUCT_QUALITY_REVIEW_TASK_TYPE in task_types
    assert QWEN_EXCLUSIVE_RIGHT_QUALITY_REVIEW_TASK_TYPE in task_types


def test_product_reject_without_article_support_is_not_coerced_to_review():
    payload = ProductFinalAdjudicationInput(
        current_product_name="Supported Product",
        current_company="Example Life",
        current_product_type="HEALTH_COMPREHENSIVE",
        current_release_year_month="2026-01",
        current_release_year_month_basis="explicit_in_article",
    )
    candidate = ProductFinalAdjudicationDecision(
        decision="reject",
        canonical_product_name="Supported Product",
        company_name="Example Life",
        product_type_code="HEALTH_COMPREHENSIVE",
        release_year_month="2026-01",
        reason="The article does not reference the claimed product at all.",
        confidence=0.92,
        provider_called=True,
    )

    result = ProductFinalAdjudicationService._coerce_recoverable_reject(candidate, payload, None)

    assert result is candidate
    assert result.decision == "reject"

    candidate = ProductFinalAdjudicationDecision(
        decision="reject",
        canonical_product_name="Signature Women Health 4.0",
        company_name="Example Insurance",
        product_type_code="WOMEN_HEALTH",
        release_year_month="2026-01",
        reason=(
            "The article explicitly mentions only another product and contains zero references to "
            "'Supported Product' or any related product."
        ),
        confidence=0.91,
        provider_called=True,
    )

    result = ProductFinalAdjudicationService._coerce_recoverable_reject(candidate, payload, None)

    assert result is candidate
    assert result.decision == "reject"

    candidate = ProductFinalAdjudicationDecision(
        decision="reject",
        canonical_product_name="Supported Product",
        company_name="Example Life",
        product_type_code="HEALTH_COMPREHENSIVE",
        release_year_month="2026-01",
        reason=(
            "The representative article makes no mention of 'Supported Product' or any related "
            "product, neither by name, description, nor implied coverage."
        ),
        confidence=0.96,
        provider_called=True,
    )

    result = ProductFinalAdjudicationService._coerce_recoverable_reject(candidate, payload, None)

    assert result is candidate
    assert result.decision == "reject"

    candidate = ProductFinalAdjudicationDecision(
        decision="reject",
        canonical_product_name="Supported Product",
        company_name="Example Life",
        product_type_code="HEALTH_COMPREHENSIVE",
        release_year_month="2026-01",
        reason=(
            "The article is a cultural briefing and mentions the insurer only as a venue location; "
            "there is no mention of any insurance product, launch, or promotion."
        ),
        confidence=0.95,
        provider_called=True,
    )

    result = ProductFinalAdjudicationService._coerce_recoverable_reject(candidate, payload, None)

    assert result is candidate
    assert result.decision == "reject"


def test_product_reject_with_clear_field_correction_can_be_coerced_to_accept():
    payload = ProductFinalAdjudicationInput(
        current_product_name="Old Product",
        current_company="Example Life",
        current_product_type="HEALTH_COMPREHENSIVE",
        current_release_year_month="2026-01",
        current_release_year_month_basis="explicit_in_article",
    )
    candidate = ProductFinalAdjudicationDecision(
        decision="reject",
        canonical_product_name="Correct Product",
        company_name="Example Life",
        product_type_code="HEALTH_COMPREHENSIVE",
        release_year_month="2026-01",
        reason="The article supports a genuine insurance product, but the current product name is wrong.",
        confidence=0.9,
        provider_called=True,
    )

    result = ProductFinalAdjudicationService._coerce_recoverable_reject(candidate, payload, None)

    assert result.decision == "accept"
    assert result.reason.startswith("recoverable_field_correction:")


def test_product_reject_with_other_product_correction_but_current_row_unsupported_stays_reject():
    payload = ProductFinalAdjudicationInput(
        current_product_name="Unsupported Dementia Product",
        current_company="Example Insurance",
        current_product_type="DEMENTIA_CARE",
        current_release_year_month="2025-02",
        current_release_year_month_basis="explicit_in_article",
    )
    candidate = ProductFinalAdjudicationDecision(
        decision="reject",
        canonical_product_name="Signature Women Health 4.0",
        company_name="Example Insurance",
        product_type_code="WOMEN_HEALTH",
        release_year_month="2026-01",
        reason=(
            "The article explicitly names only 'Signature Women Health 4.0' as a newly launched product "
            "and provides no mention of 'Unsupported Dementia Product' or any dementia-related product. "
            "The current product name and type are unsupported by evidence."
        ),
        confidence=0.9,
        provider_called=True,
    )

    result = ProductFinalAdjudicationService._coerce_recoverable_reject(candidate, payload, None)

    assert result is candidate
    assert result.decision == "reject"

    candidate = ProductFinalAdjudicationDecision(
        decision="reject",
        canonical_product_name="Cancer Survival Endorsement",
        company_name="Example Insurance",
        product_type_code="CANCER_SUPPORT_ENDORSEMENT",
        release_year_month="2026-04",
        reason=(
            "The article exclusively describes a cancer survival support endorsement, not a dental "
            "insurance product. The current product name, type, and release date are factually "
            "inconsistent with all evidence in the article. No mention or implication of dental "
            "coverage exists; aliases are unsupported by the text."
        ),
        confidence=0.95,
        provider_called=True,
    )

    result = ProductFinalAdjudicationService._coerce_recoverable_reject(candidate, payload, None)

    assert result is candidate
    assert result.decision == "reject"


def test_product_provider_accept_for_wrong_current_identity_is_rejected():
    payload = ProductFinalAdjudicationInput(
        current_product_name="Dental Insurance V",
        current_company="Example Insurance",
        current_product_type="DENTAL",
        current_release_year_month="2025-07",
        current_release_year_month_basis="earliest_related_article_month",
    )
    candidate = ProductFinalAdjudicationDecision(
        decision="accept",
        canonical_product_name="Cancer Survival Endorsement",
        company_name="Example Insurance",
        product_type_code="CANCER_SUPPORT_ENDORSEMENT",
        release_year_month="2026-04",
        reason=(
            "The article exclusively describes a cancer-related special endorsement, not a dental "
            "insurance product. The current product name, insurance type, and release date are "
            "factually inconsistent with the article's explicit content and constitute a misattribution."
        ),
        confidence=0.95,
        provider_called=True,
    )

    result = ProductFinalAdjudicationService._reject_provider_accept_for_wrong_current_identity(candidate, payload)

    assert result.decision == "reject"
    assert result.reason.startswith("provider_accept_rejected_current_product_identity_mismatch:")

    candidate = ProductFinalAdjudicationDecision(
        decision="accept",
        canonical_product_name="Cancer Survival Endorsement",
        company_name="Example Insurance",
        product_type_code="CANCER_SUPPORT_ENDORSEMENT",
        release_year_month="2026-04",
        reason=(
            "The article contains no mention of dental insurance, 'Dental Insurance V', or any "
            "variant thereof. It explicitly and repeatedly describes a cancer endorsement."
        ),
        confidence=0.95,
        provider_called=True,
    )

    result = ProductFinalAdjudicationService._reject_provider_accept_for_wrong_current_identity(candidate, payload)

    assert result.decision == "reject"
    assert result.reason.startswith("provider_accept_rejected_")


def test_product_reject_for_release_month_only_issue_is_coerced_to_review():
    payload = ProductFinalAdjudicationInput(
        current_product_name="2024 Infant Insurance",
        current_company="Example Insurance",
        current_product_type="CHILD_ADULT_CHILD",
        current_release_year_month="2025-06",
        current_release_year_month_basis="explicit_in_article",
    )
    candidate = ProductFinalAdjudicationDecision(
        decision="reject",
        canonical_product_name="2024 Infant Insurance",
        company_name="Example Insurance",
        product_type_code="CHILD_ADULT_CHILD",
        release_year_month=None,
        reason=(
            "The current release_year_month '2025-06' contradicts both the product name "
            "'2024 Infant Insurance' and the article temporal logic; the product itself is supported."
        ),
        confidence=0.9,
        provider_called=True,
    )

    result = ProductFinalAdjudicationService._coerce_recoverable_reject(candidate, payload, None)

    assert result.decision == "review"
    assert result.reason.startswith("recoverable_insurance_product_needs_review:")

    candidate = ProductFinalAdjudicationDecision(
        decision="reject",
        canonical_product_name="2024 Infant Insurance",
        company_name="Example Insurance",
        product_type_code="CHILD_ADULT_CHILD",
        release_year_month="2024-01",
        reason=(
            "The product itself is supported, but the article gives no explicit month for launch. "
            "The current release date is irreconcilable and the record invalid for downstream use."
        ),
        confidence=0.95,
        provider_called=True,
    )

    result = ProductFinalAdjudicationService._coerce_recoverable_reject(candidate, payload, None)

    assert result.decision == "review"
    assert result.reason.startswith("recoverable_insurance_product_needs_review:")


def test_exclusive_right_reject_without_subject_support_is_not_coerced_to_review():
    payload = ExclusiveRightFinalAdjudicationInput(
        current_subject_name="Unsupported Rider",
        current_company="Example Life",
        acquired_year_month="2026-01",
    )
    candidate = ExclusiveRightFinalAdjudicationDecision(
        decision="reject",
        subject_name="Unsupported Rider",
        company_name="Example Life",
        acquired_year_month="2026-01",
        reason="The article does not mention the current subject or exclusive-use-right event.",
        confidence=0.91,
        provider_called=True,
    )

    result = ExclusiveRightFinalAdjudicationService._coerce_recoverable_reject(candidate, payload, None)

    assert result is candidate
    assert result.decision == "reject"

    candidate = ExclusiveRightFinalAdjudicationDecision(
        decision="reject",
        subject_name="Unsupported Rider",
        company_name="Example Life",
        acquired_year_month="2026-01",
        reason=(
            "The article mentions the insurer only as a venue location and contains no mention of "
            "any exclusive-use-right subject, application, approval, or acquired month."
        ),
        confidence=0.93,
        provider_called=True,
    )

    result = ExclusiveRightFinalAdjudicationService._coerce_recoverable_reject(candidate, payload, None)

    assert result is candidate
    assert result.decision == "reject"
