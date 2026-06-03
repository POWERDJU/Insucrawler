from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from app.db.models import FactArticle, FactContentScreening
from app.normalizers.company_normalizer import CompanyNormalizer


@dataclass
class ScreeningResult:
    article_id: int | None
    source_type: str | None
    rule_relevance_score: float
    matched_company_names: list[str]
    matched_product_type_codes: list[str]
    matched_launch_keywords: list[str]
    matched_negative_keywords: list[str]
    is_candidate: bool
    candidate_reason: str
    llm_required_yn: bool
    llm_priority: str
    exclusive_right_score: float = 0.0
    exclusive_right_candidate_yn: bool = False
    matched_exclusive_keywords: list[str] | None = None


class ScreeningService:
    def __init__(self, rules_path: str | Path = "config/relevance_rules.yaml") -> None:
        self.rules_path = Path(rules_path)
        self.rules = self._load_rules()
        self.company_normalizer = CompanyNormalizer()

    def _load_rules(self) -> dict[str, Any]:
        if not self.rules_path.exists():
            return {}
        with self.rules_path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def screen_article(self, db: Session, article: FactArticle, body_text: str | None = None) -> ScreeningResult:
        result = self.screen_text(
            title=article.title,
            description=article.description,
            body_text=body_text,
            source_type=article.source_api,
            article_id=article.article_id,
        )
        existing = (
            db.query(FactContentScreening)
            .filter(FactContentScreening.article_id == article.article_id)
            .order_by(FactContentScreening.screening_id.desc())
            .first()
        )
        row = existing or FactContentScreening(article_id=article.article_id)
        row.source_type = result.source_type
        row.rule_relevance_score = result.rule_relevance_score
        row.matched_company_names_json = json.dumps(result.matched_company_names, ensure_ascii=False)
        row.matched_product_type_codes_json = json.dumps(result.matched_product_type_codes, ensure_ascii=False)
        row.matched_launch_keywords_json = json.dumps(result.matched_launch_keywords, ensure_ascii=False)
        row.matched_negative_keywords_json = json.dumps(result.matched_negative_keywords, ensure_ascii=False)
        row.is_candidate = result.is_candidate
        row.candidate_reason = result.candidate_reason
        row.llm_required_yn = result.llm_required_yn
        row.llm_priority = result.llm_priority
        row.exclusive_right_score = result.exclusive_right_score
        row.exclusive_right_candidate_yn = result.exclusive_right_candidate_yn
        row.matched_exclusive_keywords_json = json.dumps(result.matched_exclusive_keywords or [], ensure_ascii=False)
        if existing is None:
            db.add(row)
        db.flush()
        return result

    def screen_text(
        self,
        *,
        title: str | None,
        description: str | None,
        body_text: str | None = None,
        source_type: str | None = None,
        article_id: int | None = None,
    ) -> ScreeningResult:
        text = "\n".join(part for part in [title, description, body_text] if part)
        company_matches = self.company_normalizer.detect_all(text)
        matched_companies = list(dict.fromkeys(match.company_name_normalized for match in company_matches if match.company_name_normalized))
        product_type_matches = self._matched_product_types(text)
        launch_matches = self._matched_keywords(text, self.rules.get("launch_keywords") or [])
        coverage_matches = self._matched_keywords(text, self.rules.get("coverage_keywords") or [])
        sales_matches = self._matched_keywords(text, self.rules.get("sales_metric_keywords") or [])
        negative_matches = self._matched_keywords(text, self.rules.get("negative_keywords") or [])
        exclusive_score, exclusive_matches = self._exclusive_right_score(text, matched_companies)

        score = 0.0
        if matched_companies:
            score += 0.30
        if product_type_matches:
            score += 0.30
        if launch_matches:
            score += 0.30
        if self._has_product_name_candidate(text):
            score += 0.20
        if coverage_matches:
            score += 0.20
        if sales_matches:
            score += 0.20
        if negative_matches:
            score -= 0.50
        score = max(0.0, min(1.0, round(score, 2)))

        thresholds = self.rules.get("thresholds") or {}
        high = float(thresholds.get("high", 0.70))
        medium = float(thresholds.get("medium", 0.40))
        low = float(thresholds.get("low", 0.20))
        if score >= high:
            priority = "high"
        elif score >= medium:
            priority = "medium"
        elif score >= low:
            priority = "low"
        else:
            priority = "skip"
        llm_required = priority in {"high", "medium"}
        reason_parts = []
        if matched_companies:
            reason_parts.append("known insurer")
        if product_type_matches:
            reason_parts.append("product type")
        if launch_matches:
            reason_parts.append("launch keyword")
        if coverage_matches:
            reason_parts.append("coverage keyword")
        if sales_matches:
            reason_parts.append("sales metric")
        if negative_matches:
            reason_parts.append("negative keyword")
        return ScreeningResult(
            article_id=article_id,
            source_type=source_type,
            rule_relevance_score=score,
            matched_company_names=matched_companies,
            matched_product_type_codes=product_type_matches,
            matched_launch_keywords=launch_matches,
            matched_negative_keywords=negative_matches,
            is_candidate=priority in {"high", "medium", "low"},
            candidate_reason=", ".join(reason_parts) or "no product signal",
            llm_required_yn=llm_required,
            llm_priority=priority,
            exclusive_right_score=exclusive_score,
            exclusive_right_candidate_yn=exclusive_score >= 0.70,
            matched_exclusive_keywords=exclusive_matches,
        )

    def _matched_product_types(self, text: str) -> list[str]:
        matches: list[str] = []
        for code, keywords in (self.rules.get("product_type_keywords") or {}).items():
            if self._matched_keywords(text, keywords):
                matches.append(str(code))
        return matches

    @staticmethod
    def _matched_keywords(text: str, keywords: list[str]) -> list[str]:
        return [keyword for keyword in keywords if keyword and keyword in text]

    @staticmethod
    def _has_product_name_candidate(text: str) -> bool:
        return "보험" in text and any(trigger in text for trigger in ["출시", "신상품", "선보", "판매"])
    @staticmethod
    def _exclusive_right_score(text: str, matched_companies: list[str]) -> tuple[float, list[str]]:
        matched: list[str] = []
        score = 0.0
        exclusive_keyword_matches = [
            keyword for keyword in ["배타적사용권", "배타적 사용권", "독점사용권", "독점 사용권"] if keyword in text
        ]
        if exclusive_keyword_matches:
            score += 0.60
            matched.extend(exclusive_keyword_matches)
        acquired_keywords = ["획득", "부여", "부여받", "승인", "받았다", "인정", "인정받"]
        negated_acquired = any(
            pattern in text
            for pattern in [
                "획득 또는 부여 사실은 없다",
                "획득 사실은 없다",
                "부여 사실은 없다",
                "획득하지",
                "부여받지",
                "승인되지",
                "인정받지",
            ]
        )
        acquired_matches = [] if negated_acquired else [keyword for keyword in acquired_keywords if keyword in text]
        if acquired_matches:
            score += 0.40
            matched.extend(acquired_matches)
        if "신상품심의위원회" in text or "신상품 심의위원회" in text:
            score += 0.30
            matched.append("신상품심의위원회")
        period_matches = re.findall(r"(?:3|6|9|12)\s*개월", text)
        if period_matches:
            score += 0.20
            matched.extend(period_matches)
        if matched_companies:
            score += 0.20
        planned_only = any(keyword in text for keyword in ["신청", "추진", "예정", "도전"]) and not acquired_matches
        if planned_only:
            score -= 0.50
            matched.append("신청/예정")
        non_exclusive_patterns = ["독점판매권", "단순 판매제휴", "판매제휴", "독점 판매권"]
        if any(keyword in text for keyword in non_exclusive_patterns):
            score -= 0.50
            matched.append("not_insurance_exclusive_right")
        return max(0.0, min(1.0, round(score, 2))), list(dict.fromkeys(matched))
