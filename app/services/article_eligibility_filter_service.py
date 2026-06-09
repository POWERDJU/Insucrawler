from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.db.models import FactArticle, FactArticleSnippet
from app.services.multi_company_article_filter_service import MultiCompanyArticleFilterService
from app.utils.dates import utcnow
from app.utils.text import compact_spaces


NON_INSURANCE_FINANCIAL_INSTITUTIONS = (
    "IBK기업은행",
    "기업은행",
    "NH농협은행",
    "농협은행",
    "하나금융",
    "하나금융그룹",
    "하나은행",
    "우리금융",
    "우리금융그룹",
    "KB국민은행",
    "국민은행",
    "신한은행",
    "우리은행",
    "카카오뱅크",
    "토스뱅크",
    "케이뱅크",
    "증권",
    "카드",
    "자산운용",
    "저축은행",
    "금융지주",
    "금융투자",
)

NON_INSURANCE_PRODUCT_KEYWORDS = (
    "예금",
    "적금",
    "지수연동예금",
    "ELD",
    "KOSPI200",
    "대출",
    "징검다리론",
    "신용대출",
    "대환대출",
    "주택담보대출",
    "카드",
    "펀드",
    "ETF",
    "코스닥",
    "AI 반도체",
    "목표전환형",
    "주식",
    "채권",
    "랩",
    "신탁",
    "캠페인",
    "봉사활동",
    "스폰서데이",
    "문화체험",
    "에너지 절약",
    "구독서비스",
    "구독 서비스",
    "멤버십",
)

ROUNDUP_MARKERS = ("/", "|", "·", ";", "①", "②", "③", "▶", "◆", "◇", "■", "□", "◾", "●")

GENERAL_NON_INSURANCE_PRODUCT_KEYWORDS = (
    "건강기능식품",
    "건기식",
    "젤리",
    "영양제",
    "화장품",
    "SOTA",
    "GPT",
    "참기름",
    "멀티뷰",
    "SBS골프",
    "한국형 AI",
)

GENERAL_NON_INSURANCE_PRODUCT_NAME_KEYWORDS = (
    "건강기능식품",
    "건기식",
    "젤리",
    "영양제",
    "화장품",
    "SOTA",
    "GPT",
    "참기름",
    "멀티뷰",
    "SBS골프",
)

NON_INSURANCE_SERVICE_KEYWORDS = (
    "KT 구독서비스",
    "KT 구독 서비스",
    "구독서비스",
    "구독 서비스",
    "LG헬로비전",
    "LG 헬로비전",
    "시니어 통합 패키지",
    "가전 구독",
    "SBS골프",
    "멀티뷰",
    "스포츠 중계",
    "방송 서비스",
)

MARKETING_ONLY_KEYWORDS = (
    "TV 광고",
    "TV광고",
    "신규 TV 광고",
    "광고 캠페인",
    "브랜드 캠페인",
    "광고 영상",
    "광고 공개",
    "캠페인",
    "스폰서데이",
    "문화체험",
    "이벤트",
)

ENTERTAINMENT_MODEL_KEYWORDS = (
    "모델",
    "배우",
    "방송인",
    "광고 모델",
    "화보",
    "홍보대사",
)

GENERAL_PRODUCT_LAUNCH_KEYWORDS = (
    "출시",
    "선보",
    "공개",
    "론칭",
    "런칭",
)

INSURANCE_TITLE_FOCUS_TOKENS = (
    "보험",
    "보험상품",
    "보험출시",
    "보험판매",
    "특약",
    "담보",
    "보장",
    "생명보험",
    "손해보험",
    "화재보험",
    "건강보험",
    "암보험",
    "치매보험",
)

INDUSTRY_TREND_TITLE_MARKERS = (
    "보험사",
    "보험사는",
    "보험사들",
    "보험업계",
)

INDUSTRY_TREND_PRODUCT_MARKERS = (
    "신상품",
    "상품 설계",
    "상품 전략",
    "잇단 출시",
    "집중",
    "재편",
    "일제히",
    "새 단장",
    "경쟁",
    "치열",
)

FINANCIAL_ROUNDUP_TITLE_MARKERS = (
    "금융이모저모",
    "금융브리프",
    "금융가소식",
    "금융권소식",
    "은행보험증권",
    "플맨픽금융",
)

MULTI_INSURER_MARKET_TITLE_MARKERS = (
    "보험사일제히",
    "보험사일제",
    "보험사상품새단장",
    "보험경쟁",
    "경쟁치열",
    "여성보험경쟁",
)


def is_non_insurance_financial_product_name(name: str | None) -> bool:
    compact = re.sub(r"\s+", "", name or "").upper()
    if not compact:
        return False
    if any(token in compact for token in ["보험", "특약", "담보"]):
        return False
    return any(re.sub(r"\s+", "", keyword).upper() in compact for keyword in NON_INSURANCE_PRODUCT_KEYWORDS)


def is_non_insurance_general_product_name(name: str | None) -> bool:
    compact = re.sub(r"\s+", "", name or "").upper()
    if not compact:
        return False
    if any(token in compact for token in ["보험", "특약", "담보", "보장"]):
        return False
    return any(re.sub(r"\s+", "", keyword).upper() in compact for keyword in GENERAL_NON_INSURANCE_PRODUCT_NAME_KEYWORDS)


@dataclass(frozen=True)
class ArticleEligibilityDecision:
    eligible_for_product_extraction: bool
    eligible_for_exclusive_right_extraction: bool
    exclusion_reason: str | None = None
    detected_insurer_companies: list[str] = field(default_factory=list)
    detected_non_insurance_financial_institutions: list[str] = field(default_factory=list)
    detected_non_insurance_products: list[str] = field(default_factory=list)
    detected_non_insurance_services: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    confidence: float = 1.0

    @property
    def is_eligible(self) -> bool:
        return self.eligible_for_product_extraction and self.eligible_for_exclusive_right_extraction


class ArticleEligibilityFilterService:
    """Deterministic source-level gate before queue/batch/import.

    Raw articles are preserved. Ineligible articles are marked with existing
    article-level exclusion fields so existing dashboard/export filters exclude
    their source records.
    """

    def __init__(self, multi_company_service: MultiCompanyArticleFilterService | None = None) -> None:
        self.multi_company_service = multi_company_service or MultiCompanyArticleFilterService()

    def classify_article(self, db: Session, article: FactArticle) -> ArticleEligibilityDecision:
        text = self._article_text(db, article)
        return self.classify_text(db, text)

    def classify_text(self, db: Session, text: str | None) -> ArticleEligibilityDecision:
        value = text or ""
        multi = self.multi_company_service.classify_text(db, value)
        non_insurers = self._detect_non_insurance_institutions(value)
        non_insurance_products = self._detect_non_insurance_products(value)
        general_non_insurance_products = self._detect_general_non_insurance_products(value)
        non_insurance_services = self._detect_non_insurance_services(value)
        roundup = self._looks_like_roundup(value)
        recoverable_exclusive_right = (
            not multi.is_multi_company
            and self._has_recoverable_exclusive_right_event(value)
        )
        primary_non_insurance = self._primary_non_insurance_financial_context(
            value,
            non_insurers=non_insurers,
            non_insurance_products=non_insurance_products,
        )
        primary_general_non_insurance = self._primary_general_non_insurance_product_context(
            value,
            general_non_insurance_products=general_non_insurance_products,
        )
        evidence = self._evidence(value)

        if self._looks_like_financial_roundup_title(
            value,
            non_insurers=non_insurers,
            non_insurance_products=non_insurance_products,
            insurer_companies=multi.company_names,
        ) and not recoverable_exclusive_right:
            return ArticleEligibilityDecision(
                eligible_for_product_extraction=False,
                eligible_for_exclusive_right_extraction=False,
                exclusion_reason="multi_financial_institution_roundup",
                detected_insurer_companies=multi.company_names,
                detected_non_insurance_financial_institutions=non_insurers,
                detected_non_insurance_products=non_insurance_products + general_non_insurance_products,
                detected_non_insurance_services=non_insurance_services,
                evidence=evidence,
                confidence=0.95,
            )
        if self._looks_like_multi_insurer_market_article(value, insurer_companies=multi.company_names) and not recoverable_exclusive_right:
            return ArticleEligibilityDecision(
                eligible_for_product_extraction=False,
                eligible_for_exclusive_right_extraction=False,
                exclusion_reason="industry_trend_multi_company_article",
                detected_insurer_companies=multi.company_names,
                detected_non_insurance_financial_institutions=non_insurers,
                detected_non_insurance_products=non_insurance_products + general_non_insurance_products,
                detected_non_insurance_services=non_insurance_services,
                evidence=evidence,
                confidence=0.9,
            )

        if self._looks_like_sports_broadcast_service(value, non_insurance_services):
            return ArticleEligibilityDecision(
                eligible_for_product_extraction=False,
                eligible_for_exclusive_right_extraction=False,
                exclusion_reason="sports_broadcast_service_article",
                detected_insurer_companies=multi.company_names,
                detected_non_insurance_financial_institutions=non_insurers,
                detected_non_insurance_products=non_insurance_products + general_non_insurance_products,
                detected_non_insurance_services=non_insurance_services,
                evidence=evidence,
                confidence=0.95,
            )
        if self._looks_like_subscription_service(value, non_insurance_services):
            return ArticleEligibilityDecision(
                eligible_for_product_extraction=False,
                eligible_for_exclusive_right_extraction=False,
                exclusion_reason="subscription_service_article",
                detected_insurer_companies=multi.company_names,
                detected_non_insurance_financial_institutions=non_insurers,
                detected_non_insurance_products=non_insurance_products + general_non_insurance_products,
                detected_non_insurance_services=non_insurance_services,
                evidence=evidence,
                confidence=0.95,
            )
        if self._looks_like_marketing_only_article(value) and not self._has_clear_product_launch_context(value):
            return ArticleEligibilityDecision(
                eligible_for_product_extraction=False,
                eligible_for_exclusive_right_extraction=False,
                exclusion_reason="campaign_or_ad_only_article",
                detected_insurer_companies=multi.company_names,
                detected_non_insurance_financial_institutions=non_insurers,
                detected_non_insurance_products=non_insurance_products + general_non_insurance_products,
                detected_non_insurance_services=non_insurance_services,
                evidence=evidence,
                confidence=0.9,
            )
        if self._looks_like_entertainment_model_article(value) and not self._has_insurance_product_context(value):
            return ArticleEligibilityDecision(
                eligible_for_product_extraction=False,
                eligible_for_exclusive_right_extraction=False,
                exclusion_reason="entertainment_model_article",
                detected_insurer_companies=multi.company_names,
                detected_non_insurance_financial_institutions=non_insurers,
                detected_non_insurance_products=non_insurance_products + general_non_insurance_products,
                detected_non_insurance_services=non_insurance_services,
                evidence=evidence,
                confidence=0.9,
            )

        if self._looks_like_industry_trend_product_roundup(value) and not recoverable_exclusive_right:
            return ArticleEligibilityDecision(
                eligible_for_product_extraction=False,
                eligible_for_exclusive_right_extraction=False,
                exclusion_reason="industry_trend_multi_company_article",
                detected_insurer_companies=multi.company_names,
                detected_non_insurance_financial_institutions=non_insurers,
                detected_non_insurance_products=non_insurance_products + general_non_insurance_products,
                detected_non_insurance_services=non_insurance_services,
                evidence=evidence,
                confidence=0.85,
            )
        if multi.is_multi_company and not recoverable_exclusive_right:
            return ArticleEligibilityDecision(
                eligible_for_product_extraction=False,
                eligible_for_exclusive_right_extraction=False,
                exclusion_reason="multi_company_article",
                detected_insurer_companies=multi.company_names,
                detected_non_insurance_financial_institutions=non_insurers,
                detected_non_insurance_products=non_insurance_products,
                detected_non_insurance_services=non_insurance_services,
                evidence=evidence,
                confidence=0.95,
            )
        if multi.company_names and non_insurers and roundup:
            return ArticleEligibilityDecision(
                eligible_for_product_extraction=False,
                eligible_for_exclusive_right_extraction=False,
                exclusion_reason="multi_financial_institution_roundup",
                detected_insurer_companies=multi.company_names,
                detected_non_insurance_financial_institutions=non_insurers,
                detected_non_insurance_products=non_insurance_products,
                detected_non_insurance_services=non_insurance_services,
                evidence=evidence,
                confidence=0.95,
            )
        if primary_non_insurance and non_insurance_products and not self._has_insurance_product_context(value):
            return ArticleEligibilityDecision(
                eligible_for_product_extraction=False,
                eligible_for_exclusive_right_extraction=False,
                exclusion_reason="non_insurance_financial_product",
                detected_insurer_companies=multi.company_names,
                detected_non_insurance_financial_institutions=non_insurers,
                detected_non_insurance_products=non_insurance_products,
                detected_non_insurance_services=non_insurance_services,
                evidence=evidence,
                confidence=0.95,
            )
        if primary_general_non_insurance:
            return ArticleEligibilityDecision(
                eligible_for_product_extraction=False,
                eligible_for_exclusive_right_extraction=False,
                exclusion_reason="non_insurance_product_article",
                detected_insurer_companies=multi.company_names,
                detected_non_insurance_financial_institutions=non_insurers,
                detected_non_insurance_products=general_non_insurance_products,
                detected_non_insurance_services=non_insurance_services,
                evidence=evidence,
                confidence=0.9,
            )
        if non_insurers and primary_non_insurance and self._has_insurance_product_context(value):
            return ArticleEligibilityDecision(
                eligible_for_product_extraction=False,
                eligible_for_exclusive_right_extraction=False,
                exclusion_reason="multi_financial_institution_roundup",
                detected_insurer_companies=multi.company_names,
                detected_non_insurance_financial_institutions=non_insurers,
                detected_non_insurance_products=non_insurance_products,
                detected_non_insurance_services=non_insurance_services,
                evidence=evidence,
                confidence=0.9,
            )
        if non_insurance_products and roundup and not self._has_insurance_product_context(value):
            return ArticleEligibilityDecision(
                eligible_for_product_extraction=False,
                eligible_for_exclusive_right_extraction=False,
                exclusion_reason="non_insurance_financial_product",
                detected_insurer_companies=multi.company_names,
                detected_non_insurance_financial_institutions=non_insurers,
                detected_non_insurance_products=non_insurance_products,
                detected_non_insurance_services=non_insurance_services,
                evidence=evidence,
                confidence=0.9,
            )
        return ArticleEligibilityDecision(
            eligible_for_product_extraction=True,
            eligible_for_exclusive_right_extraction=True,
            detected_insurer_companies=multi.company_names,
            detected_non_insurance_financial_institutions=non_insurers,
            detected_non_insurance_products=non_insurance_products,
            detected_non_insurance_services=non_insurance_services,
            evidence=evidence,
            confidence=0.8,
        )

    def mark_article(self, db: Session, article: FactArticle, decision: ArticleEligibilityDecision | None = None) -> ArticleEligibilityDecision:
        decision = decision or self.classify_article(db, article)
        article.multi_company_article_yn = not decision.is_eligible
        companies = {
            "insurers": decision.detected_insurer_companies,
            "non_insurance_financial_institutions": decision.detected_non_insurance_financial_institutions,
            "non_insurance_products": decision.detected_non_insurance_products,
            "non_insurance_services": decision.detected_non_insurance_services,
        }
        article.multi_company_company_names_json = json.dumps(companies, ensure_ascii=False)
        if not decision.is_eligible:
            article.multi_company_detected_at = utcnow()
            article.extraction_status = "excluded_article_eligibility"
            article.extraction_exclusion_reason = decision.exclusion_reason
        db.flush()
        return decision

    def is_article_eligible(self, db: Session, article: FactArticle) -> bool:
        if bool(article.multi_company_article_yn):
            return False
        if article.extraction_exclusion_reason in {
            "multi_company_article",
            "industry_trend_multi_company_article",
            "multi_financial_institution_roundup",
            "non_insurance_financial_product",
            "non_insurance_product_article",
            "non_insurance_article",
            "marketing_only_article",
            "campaign_or_ad_only_article",
            "subscription_service_article",
            "entertainment_model_article",
            "sports_broadcast_service_article",
        }:
            return False
        decision = self.classify_article(db, article)
        return decision.is_eligible

    def _article_text(self, db: Session, article: FactArticle) -> str:
        snippets = (
            db.query(FactArticleSnippet.snippet_text)
            .filter(FactArticleSnippet.article_id == article.article_id)
            .order_by(FactArticleSnippet.snippet_id)
            .all()
            if article.article_id
            else []
        )
        snippet_text = "\n".join(row[0] for row in snippets if row[0])
        return "\n".join(part for part in [article.title, article.description, snippet_text] if part)

    def _detect_non_insurance_institutions(self, text: str) -> list[str]:
        found: list[str] = []
        compact = re.sub(r"\s+", "", text or "")
        for name in NON_INSURANCE_FINANCIAL_INSTITUTIONS:
            if re.sub(r"\s+", "", name) in compact and name not in found:
                found.append(name)
        return found

    def _detect_non_insurance_products(self, text: str) -> list[str]:
        found: list[str] = []
        compact = re.sub(r"\s+", "", text or "")
        for keyword in NON_INSURANCE_PRODUCT_KEYWORDS:
            if re.sub(r"\s+", "", keyword).upper() in compact.upper() and keyword not in found:
                found.append(keyword)
        match = re.search(r"KOSPI\s*200\s*지수연동예금", text or "", flags=re.IGNORECASE)
        if match and "KOSPI200 지수연동예금" not in found:
            found.append("KOSPI200 지수연동예금")
        return found

    def _detect_general_non_insurance_products(self, text: str) -> list[str]:
        found: list[str] = []
        compact = re.sub(r"\s+", "", text or "").upper()
        for keyword in GENERAL_NON_INSURANCE_PRODUCT_KEYWORDS:
            if re.sub(r"\s+", "", keyword).upper() in compact and keyword not in found:
                found.append(keyword)
        return found

    def _detect_non_insurance_services(self, text: str) -> list[str]:
        found: list[str] = []
        compact = re.sub(r"\s+", "", text or "").upper()
        for keyword in NON_INSURANCE_SERVICE_KEYWORDS:
            if re.sub(r"\s+", "", keyword).upper() in compact and keyword not in found:
                found.append(keyword)
        return found

    def _looks_like_roundup(self, text: str) -> bool:
        if any(marker in (text or "") for marker in ROUNDUP_MARKERS):
            return True
        return bool(re.search(r"(^|\n)\s*[▶◆◇■□◾●-]\s*", text or ""))

    def _primary_non_insurance_financial_context(
        self,
        text: str,
        *,
        non_insurers: list[str],
        non_insurance_products: list[str],
    ) -> bool:
        first_line = next((line.strip() for line in re.split(r"[\n\r]+", text or "") if line.strip()), "")
        if not first_line:
            return False
        compact_title = re.sub(r"\s+", "", first_line).upper()
        title_has_non_insurer = any(re.sub(r"\s+", "", item).upper() in compact_title for item in non_insurers)
        title_has_non_insurance_product = any(
            re.sub(r"\s+", "", item).upper() in compact_title for item in non_insurance_products
        )
        if not (title_has_non_insurer or title_has_non_insurance_product):
            return False
        insurance_focus_tokens = (
            "보험출시",
            "보험상품",
            "보험판매",
            "보험서비스",
            "보험시판",
            "보험전용",
            "전용보험",
            "보험가입",
            "보험출범",
            "특약",
            "담보",
            "생명보험",
            "손해보험",
            "화재보험",
        )
        return not any(token.upper() in compact_title for token in insurance_focus_tokens)

    def _primary_general_non_insurance_product_context(
        self,
        text: str,
        *,
        general_non_insurance_products: list[str],
    ) -> bool:
        if not general_non_insurance_products:
            return False
        first_line = next((line.strip() for line in re.split(r"[\n\r]+", text or "") if line.strip()), "")
        if not first_line:
            return False
        compact_title = re.sub(r"\s+", "", first_line).upper()
        has_launch = any(re.sub(r"\s+", "", keyword).upper() in compact_title for keyword in GENERAL_PRODUCT_LAUNCH_KEYWORDS)
        if not has_launch:
            return False
        if self._title_has_insurance_product_focus(first_line):
            return False
        return any(re.sub(r"\s+", "", item).upper() in compact_title for item in general_non_insurance_products)

    def _looks_like_subscription_service(self, text: str, services: list[str]) -> bool:
        first_line = next((line.strip() for line in re.split(r"[\n\r]+", text or "") if line.strip()), "")
        compact_title = re.sub(r"\s+", "", first_line or text or "")
        if not any("구독" in item or "LG헬로비전" in item or "시니어" in item for item in services):
            return False
        if self._title_has_insurance_product_focus(first_line):
            return False
        return any(token in compact_title for token in ["구독", "LG헬로비전", "헬로비전", "시니어통합패키지", "가전구독"])

    def _looks_like_sports_broadcast_service(self, text: str, services: list[str]) -> bool:
        first_line = next((line.strip() for line in re.split(r"[\n\r]+", text or "") if line.strip()), "")
        compact_title = re.sub(r"\s+", "", first_line or text or "")
        if self._title_has_insurance_product_focus(first_line):
            return False
        return any(token in compact_title for token in ["SBS골프", "멀티뷰", "스포츠중계", "방송서비스"]) or any(
            item in {"SBS골프", "멀티뷰"} for item in services
        )

    def _looks_like_marketing_only_article(self, text: str) -> bool:
        value = compact_spaces(text)
        if not value:
            return False
        return any(keyword in value for keyword in MARKETING_ONLY_KEYWORDS)

    def _looks_like_entertainment_model_article(self, text: str) -> bool:
        value = compact_spaces(text)
        if not value:
            return False
        return any(keyword in value for keyword in ENTERTAINMENT_MODEL_KEYWORDS)

    def _title_has_insurance_product_focus(self, title: str) -> bool:
        compact = re.sub(r"\s+", "", title or "").upper()
        return any(re.sub(r"\s+", "", token).upper() in compact for token in INSURANCE_TITLE_FOCUS_TOKENS)

    def _looks_like_industry_trend_product_roundup(self, text: str) -> bool:
        first_line = next((line.strip() for line in re.split(r"[\n\r]+", text or "") if line.strip()), "")
        if not first_line:
            return False
        compact_title = re.sub(r"\s+", "", first_line)
        has_industry_marker = any(re.sub(r"\s+", "", marker) in compact_title for marker in INDUSTRY_TREND_TITLE_MARKERS)
        has_product_marker = any(re.sub(r"\s+", "", marker) in compact_title for marker in INDUSTRY_TREND_PRODUCT_MARKERS)
        return has_industry_marker and has_product_marker

    def _has_recoverable_exclusive_right_event(self, text: str) -> bool:
        value = compact_spaces(text)
        if not value:
            return False
        compact = re.sub(r"\s+", "", value)
        has_exclusive = any(
            token in compact
            for token in (
                "배타적사용권",
                "배타적사용권을",
                "배타적사용권획득",
                "독점판매권",
                "독점사용권",
            )
        ) or "exclusive use right" in value.casefold() or "exclusive-use-right" in value.casefold()
        if not has_exclusive:
            return False
        has_acquired = any(
            token in compact
            for token in (
                "획득",
                "부여",
                "인정",
                "승인",
                "확보",
                "취득",
            )
        ) or any(token in value.casefold() for token in ("acquired", "granted", "obtained", "secured"))
        if not has_acquired:
            return False
        subject_nearby = bool(
            re.search(r"['\"‘“][^'\"’”]{2,90}['\"’”].{0,80}(?:배타적\s*사용권|exclusive[- ]use[- ]right)", value, re.IGNORECASE)
            or re.search(r"[가-힣A-Za-z0-9()·\[\] -]{2,90}(?:특약|담보|보험|서비스|상품|구조|제도).{0,80}(?:배타적\s*사용권|exclusive[- ]use[- ]right)", value, re.IGNORECASE)
            or re.search(r"(?:for|for the) ['\"‘“][^'\"’”]{2,90}['\"’”]", value, re.IGNORECASE)
        )
        return subject_nearby

    def _looks_like_financial_roundup_title(
        self,
        text: str,
        *,
        non_insurers: list[str],
        non_insurance_products: list[str],
        insurer_companies: list[str],
    ) -> bool:
        first_line = next((line.strip() for line in re.split(r"[\n\r]+", text or "") if line.strip()), "")
        if not first_line:
            return False
        compact_title = re.sub(r"\s+", "", first_line)
        has_roundup_marker = any(marker in compact_title for marker in FINANCIAL_ROUNDUP_TITLE_MARKERS)
        if not has_roundup_marker:
            return False
        return bool(non_insurers or non_insurance_products or insurer_companies or "보험" in compact_title)

    def _looks_like_multi_insurer_market_article(self, text: str, *, insurer_companies: list[str]) -> bool:
        first_line = next((line.strip() for line in re.split(r"[\n\r]+", text or "") if line.strip()), "")
        if not first_line:
            return False
        compact_title = re.sub(r"\s+", "", first_line)
        if any(marker in compact_title for marker in MULTI_INSURER_MARKET_TITLE_MARKERS):
            return "보험" in compact_title
        if "보험사" in compact_title and any(marker in compact_title for marker in ("일제히", "새단장", "경쟁", "치열")):
            return True
        if re.search(r"(?:이어|까지).*(?:보험|특약|상품).*경쟁", first_line):
            return True
        return len(insurer_companies) > 1 and any(marker in compact_title for marker in ("경쟁", "치열", "일제히", "새단장"))

    def _has_insurance_product_context(self, text: str) -> bool:
        compact = re.sub(r"\s+", "", text or "")
        return any(token in compact for token in ["보험출시", "보험상품", "특약", "담보", "보장서비스", "상해및질병보장"])

    def _has_clear_product_launch_context(self, text: str) -> bool:
        compact = re.sub(r"\s+", "", text or "")
        return any(
            token in compact
            for token in [
                "보험상품출시",
                "신상품출시",
                "상품출시",
                "판매개시",
                "출시했다",
                "출시한다",
                "특약",
                "담보",
                "배타적사용권",
            ]
        ) and any(token in compact for token in ["보험", "특약", "담보", "보장"])

    def _evidence(self, text: str) -> list[str]:
        lines = [line.strip() for line in re.split(r"[\n\r]+", text or "") if line.strip()]
        if lines:
            return lines[:5]
        return [(text or "")[:300]] if text else []
