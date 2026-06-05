from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import DimCompany, FactArticle, FactArticleSnippet
from app.normalizers.company_normalizer import CompanyMatch, CompanyNormalizer
from app.utils.dates import utcnow


@dataclass(frozen=True)
class MultiCompanyArticleResult:
    is_multi_company: bool
    company_names: list[str]
    company_count: int


class MultiCompanyArticleFilterService:
    """Deterministic article-level gate for articles mentioning multiple insurers.

    The policy is intentionally article/source scoped. A multi-company article is
    excluded from new extraction queues, but canonical products/events are kept
    when they also have non-multi-company evidence.
    """

    def __init__(self, normalizer: CompanyNormalizer | None = None) -> None:
        self.normalizer = normalizer or CompanyNormalizer()

    def classify_article(self, db: Session, article: FactArticle) -> MultiCompanyArticleResult:
        snippets = (
            db.query(FactArticleSnippet.snippet_text)
            .filter(FactArticleSnippet.article_id == article.article_id)
            .order_by(FactArticleSnippet.snippet_id)
            .all()
            if article.article_id
            else []
        )
        snippet_text = "\n".join(row[0] for row in snippets if row[0])
        text = "\n".join(part for part in [article.title, article.description, snippet_text] if part)
        return self.classify_text(db, text)

    def classify_text(self, db: Session, text: str | None) -> MultiCompanyArticleResult:
        names = self._insurer_names(db, self.normalizer.detect_all_with_positions(text))
        return MultiCompanyArticleResult(
            is_multi_company=len(names) >= 2,
            company_names=names,
            company_count=len(names),
        )

    def mark_article(self, db: Session, article: FactArticle, result: MultiCompanyArticleResult | None = None) -> MultiCompanyArticleResult:
        result = result or self.classify_article(db, article)
        article.multi_company_article_yn = result.is_multi_company
        article.multi_company_company_names_json = json.dumps(result.company_names, ensure_ascii=False)
        if result.is_multi_company:
            article.multi_company_detected_at = utcnow()
            article.extraction_status = "excluded_multi_company"
            article.extraction_exclusion_reason = "multiple insurer companies detected in article"
        db.flush()
        return result

    def audit_articles(self, db: Session, *, date_from: str | None = None, date_to: str | None = None, apply: bool = False) -> list[dict]:
        query = db.query(FactArticle).order_by(FactArticle.article_id)
        if date_from:
            query = query.filter(FactArticle.pub_date >= datetime.fromisoformat(date_from))
        if date_to:
            query = query.filter(FactArticle.pub_date <= datetime.fromisoformat(date_to))
        rows: list[dict] = []
        for article in query.all():
            result = self.classify_article(db, article)
            rows.append(
                {
                    "article_id": article.article_id,
                    "article_title": article.title,
                    "is_multi_company": result.is_multi_company,
                    "company_count": result.company_count,
                    "company_names": "|".join(result.company_names),
                    "current_status": article.extraction_status,
                    "proposed_status": "excluded_multi_company" if result.is_multi_company else article.extraction_status,
                    "action": "flag_article" if result.is_multi_company else "keep",
                }
            )
            if apply:
                self.mark_article(db, article, result)
        if apply:
            db.commit()
        return rows

    def _insurer_names(self, db: Session, matches: list[CompanyMatch]) -> list[str]:
        names: list[str] = []
        for match in matches:
            if not self._is_countable_insurer(db, match):
                continue
            name = match.company_name_normalized
            if name and name not in names:
                names.append(name)
        return names

    @staticmethod
    def _is_countable_insurer(db: Session, match: CompanyMatch) -> bool:
        if not match.is_known_insurer or not match.company_name_normalized:
            return False
        if match.is_short_alias or match.match_type == "short_alias":
            return False
        if int(match.alias_length or 0) < 4:
            return False
        company = (
            db.query(DimCompany)
            .filter(DimCompany.company_name_normalized == match.company_name_normalized)
            .first()
        )
        if not company:
            return False
        if (company.include_in_product_news_default or "Y") != "Y":
            return False
        role = (company.company_role or "").lower()
        if any(token in role for token in ["association", "agency", "partner", "platform"]):
            return False
        return True
