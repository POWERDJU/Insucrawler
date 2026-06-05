from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.db import repository
from app.db.models import DimCompany, FactArticle, FactArticleSnippet, FactProductArticle, FactProductCandidateCluster
from app.db.repository import company_aliases_for_company
from app.extractors.product_launch_candidate import extract_launch_product_candidates
from app.normalizers.product_name_normalizer import normalize_product_name, normalize_product_name_core, product_core_key_candidates
from app.services.screening_service import ScreeningResult
from app.services.company_attribution_service import CompanyAttributionService
from app.services.multi_company_article_filter_service import MultiCompanyArticleFilterService
from app.services.product_attribution_guard_service import ProductAttributionGuardService
from app.services.product_company_eligibility import is_product_news_eligible_company


class ProductCandidateClusterService:
    def upsert_for_article(
        self,
        db: Session,
        article: FactArticle,
        screening: ScreeningResult | None = None,
        snippets: list[Any] | None = None,
    ) -> FactProductCandidateCluster | None:
        if not article.multi_company_company_names_json and not bool(article.multi_company_article_yn):
            result = MultiCompanyArticleFilterService().mark_article(db, article)
            if result.is_multi_company:
                return None
        if bool(article.multi_company_article_yn):
            return None
        local_text = "\n".join(part for part in [article.description, *[s.snippet_text for s in snippets or []]] if part)
        text = "\n".join(part for part in [article.title, local_text] if part)
        candidate_name = self._candidate_product_name(text)
        guard = ProductAttributionGuardService()
        if guard.is_generic_product_name(candidate_name) and guard.is_marketing_only_article(
            guard.extract_product_local_window(article=article, product_name=candidate_name, source_text=local_text)
        ):
            return None
        company = self._detect_company(
            db,
            local_text=local_text or text,
            article_title=article.title,
            article_description=article.description,
            full_text=text,
            screening=screening,
            candidate_product_name=candidate_name,
        )
        if not company and not candidate_name:
            return None
        aliases = company_aliases_for_company(company)
        normalized_name = normalize_product_name(candidate_name, aliases) if candidate_name else None
        candidate_keys = product_core_key_candidates(normalized_name, aliases) if normalized_name else []
        core_key = candidate_keys[-1] if candidate_keys else (normalize_product_name_core(normalized_name, aliases) if normalized_name else None)
        query = db.query(FactProductCandidateCluster)
        if company:
            query = query.filter(FactProductCandidateCluster.company_id == company.company_id)
        else:
            query = query.filter(FactProductCandidateCluster.company_id.is_(None))
        if candidate_keys:
            query = query.filter(FactProductCandidateCluster.product_core_key.in_(candidate_keys))
        elif core_key:
            query = query.filter(FactProductCandidateCluster.product_core_key == core_key)
        else:
            query = query.filter(FactProductCandidateCluster.candidate_product_name == candidate_name)
        cluster = query.first()
        if not cluster:
            cluster = FactProductCandidateCluster(
                company_id=company.company_id if company else None,
                product_core_key=core_key,
                candidate_product_name=normalized_name or candidate_name,
                candidate_company_name=company.company_name_normalized if company else None,
                article_count=0,
                source_article_ids_json="[]",
                screening_score=screening.rule_relevance_score if screening else 0.0,
                llm_status="pending",
            )
            db.add(cluster)
            db.flush()
        article_ids = set(json.loads(cluster.source_article_ids_json or "[]"))
        article_ids.add(article.article_id)
        cluster.source_article_ids_json = json.dumps(sorted(article_ids), ensure_ascii=False)
        cluster.article_count = len(article_ids)
        if article.pub_date:
            if not cluster.earliest_article_date or article.pub_date < cluster.earliest_article_date:
                cluster.earliest_article_date = article.pub_date
            if not cluster.latest_article_date or article.pub_date > cluster.latest_article_date:
                cluster.latest_article_date = article.pub_date
        if screening:
            cluster.screening_score = max(float(cluster.screening_score or 0), screening.rule_relevance_score)
        db.flush()
        return cluster

    def build_cluster_llm_input(self, db: Session, cluster: FactProductCandidateCluster, max_articles: int = 5, max_chars: int = 5000) -> str:
        raw_article_ids = [int(item) for item in json.loads(cluster.source_article_ids_json or "[]")]
        if raw_article_ids:
            clean_rows = (
                db.query(FactArticle.article_id)
                .filter(
                    FactArticle.article_id.in_(raw_article_ids),
                    FactArticle.multi_company_article_yn == False,  # noqa: E712
                )
                .order_by(FactArticle.article_id)
                .all()
            )
            article_ids = [int(row[0]) for row in clean_rows][:max_articles]
        else:
            article_ids = []
        snippets = (
            db.query(FactArticleSnippet)
            .filter(FactArticleSnippet.article_id.in_(article_ids))
            .order_by(FactArticleSnippet.article_id, FactArticleSnippet.snippet_id)
            .all()
            if article_ids
            else []
        )
        articles = db.query(FactArticle).filter(FactArticle.article_id.in_(article_ids)).all() if article_ids else []
        payload = {
            "target_type": "product_candidate_cluster",
            "candidate_cluster_id": cluster.candidate_cluster_id,
            "candidate_company_name": cluster.candidate_company_name,
            "candidate_product_name": cluster.candidate_product_name,
            "article_count": cluster.article_count,
            "articles": [
                {
                    "article_id": article.article_id,
                    "title": article.title,
                    "description": article.description,
                    "pub_date": article.pub_date.isoformat() if article.pub_date else None,
                }
                for article in articles
            ],
            "snippets": [
                {
                    "article_id": snippet.article_id,
                    "snippet_type": snippet.snippet_type,
                    "snippet_text": snippet.snippet_text,
                }
                for snippet in snippets
            ],
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        return text[:max_chars]

    def link_article_to_existing_products(
        self,
        db: Session,
        cluster: FactProductCandidateCluster,
        article: FactArticle,
        *,
        confidence_total: float = 0.0,
    ) -> list[int]:
        article_ids = [int(item) for item in json.loads(cluster.source_article_ids_json or "[]") if int(item) != article.article_id]
        if not article_ids:
            return []
        article_ids = [
            int(row[0])
            for row in db.query(FactArticle.article_id)
            .filter(FactArticle.article_id.in_(article_ids), FactArticle.multi_company_article_yn == False)  # noqa: E712
            .all()
        ]
        if not article_ids:
            return []
        rows = (
            db.query(FactProductArticle.product_id)
            .filter(FactProductArticle.article_id.in_(article_ids))
            .distinct()
            .all()
        )
        product_ids = [int(row[0]) for row in rows if row[0] is not None]
        for product_id in product_ids:
            repository.link_product_article(
                db,
                product_id,
                article.article_id,
                confidence_total=confidence_total,
                needs_review=False,
                evidence_summary="linked from extracted product candidate cluster",
            )
        return product_ids

    @staticmethod
    def _candidate_product_name(text: str) -> str | None:
        candidates = extract_launch_product_candidates(text)
        if candidates:
            return candidates[0].normalized_name or candidates[0].raw_name
        first_line = (text or "").splitlines()[0] if text else ""
        match = re.search(r"(.+?)\s*(?:신규\s*)?(?:출시|선보|내놨|판매\s*개시)", first_line)
        if match:
            candidate = re.sub(r"^[^,，]+[,，]\s*", "", match.group(1)).strip()
            return candidate or None
        return None

    @staticmethod
    def _detect_company(
        db: Session,
        *,
        local_text: str,
        article_title: str | None = None,
        article_description: str | None = None,
        full_text: str | None = None,
        screening: ScreeningResult | None = None,
        candidate_product_name: str | None = None,
    ) -> DimCompany | None:
        names = screening.matched_company_names if screening else []
        attribution = CompanyAttributionService().resolve_company_for_context(
            db,
            local_text=local_text,
            article_title=article_title,
            article_description=article_description,
            full_text=full_text,
            product_or_subject_name=candidate_product_name,
            company_candidates=names,
        )
        if attribution.needs_review or not attribution.company_name_normalized:
            return None
        if attribution.basis in {"company_candidates", "raw_candidate"}:
            return None
        company = db.query(DimCompany).filter(DimCompany.company_name_normalized == attribution.company_name_normalized).first()
        if not is_product_news_eligible_company(company):
            return None
        return company
