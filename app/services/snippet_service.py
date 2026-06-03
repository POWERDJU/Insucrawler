from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import FactArticle, FactArticleSnippet


SNIPPET_KEYWORDS = {
    "launch": ["신상품", "신규 출시", "출시", "선보였다", "내놨다", "판매 개시"],
    "coverage": ["보장", "진단비", "수술비", "입원", "치료", "사망", "후유장해", "배상책임", "보험금", "최대"],
    "sales_metric": ["판매건수", "판매 건수", "월초보험료", "보장월초보험료", "누적보험료", "초회보험료", "돌파"],
    "underwriting": ["간편고지", "유병자", "무고지", "가입연령", "고령자", "심사"],
    "channel": ["다이렉트", "모바일", "온라인", "앱", "GA", "설계사"],
    "marketing": ["할인", "이벤트", "혜택", "프로모션", "마케팅"],
}

SNIPPET_KEYWORDS.update(
    {
        "exclusive_right": ["배타적사용권", "배타적 사용권", "독점사용권", "독점 사용권", "신상품심의위원회", "신상품 심의위원회", "독창성", "획득", "부여", "부여받", "승인", "인정"],
        "exclusive_period": ["3개월", "6개월", "9개월", "12개월", "개월간", "기간"],
        "exclusive_acquired_date": ["획득", "부여", "승인", "받았다", "인정", "최근", "지난", "올해", "이달"],
        "exclusive_feature": ["새로운 위험", "신규 담보", "새로운 급부", "급부방식", "제도", "서비스", "독창성", "혁신성"],
    }
)


@dataclass
class Snippet:
    snippet_type: str
    snippet_text: str
    sentence_index: int
    matched_keywords: list[str]


class SnippetService:
    def __init__(self, context_sentences: int | None = None, max_chars: int | None = None) -> None:
        self.context_sentences = context_sentences if context_sentences is not None else int(os.getenv("SNIPPET_CONTEXT_SENTENCES", "1"))
        self.max_chars = max_chars if max_chars is not None else int(os.getenv("MAX_SNIPPET_CHARS_PER_ARTICLE", "3000"))

    def extract_for_article(self, db: Session, article: FactArticle, body_text: str | None = None) -> list[Snippet]:
        snippets = self.extract_snippets("\n".join(part for part in [article.title, article.description, body_text] if part))
        db.query(FactArticleSnippet).filter(FactArticleSnippet.article_id == article.article_id).delete(synchronize_session=False)
        for snippet in snippets:
            db.add(
                FactArticleSnippet(
                    article_id=article.article_id,
                    snippet_type=snippet.snippet_type,
                    snippet_text=snippet.snippet_text,
                    sentence_index=snippet.sentence_index,
                    matched_keywords_json=json.dumps(snippet.matched_keywords, ensure_ascii=False),
                )
            )
        db.flush()
        return snippets

    def extract_snippets(self, text: str | None) -> list[Snippet]:
        sentences = self._split_sentences(text or "")
        snippets: list[Snippet] = []
        seen: set[tuple[str, int]] = set()
        total_chars = 0
        for idx, sentence in enumerate(sentences):
            for snippet_type, keywords in SNIPPET_KEYWORDS.items():
                matched = [keyword for keyword in keywords if keyword in sentence]
                if not matched:
                    continue
                key = (snippet_type, idx)
                if key in seen:
                    continue
                start = max(0, idx - self.context_sentences)
                end = min(len(sentences), idx + self.context_sentences + 1)
                snippet_text = " ".join(sentences[start:end]).strip()
                if not snippet_text:
                    continue
                if total_chars + len(snippet_text) > self.max_chars:
                    continue
                total_chars += len(snippet_text)
                seen.add(key)
                snippets.append(Snippet(snippet_type, snippet_text, idx, matched))
        if not snippets and sentences:
            summary = " ".join(sentences[:2])[: self.max_chars]
            snippets.append(Snippet("article_summary", summary, 0, []))
        return snippets

    def build_llm_input(
        self,
        *,
        title: str | None,
        description: str | None,
        source_type: str | None,
        article_date: Any = None,
        company_candidates: list[str] | None = None,
        product_type_candidates: list[str] | None = None,
        snippets: list[Snippet] | None = None,
    ) -> str:
        grouped: dict[str, list[str]] = {}
        for snippet in snippets or []:
            grouped.setdefault(snippet.snippet_type, []).append(snippet.snippet_text)
        payload = {
            "title": title,
            "description": description,
            "source_type": source_type,
            "article_date": article_date.isoformat() if hasattr(article_date, "isoformat") else article_date,
            "company_candidates": company_candidates or [],
            "product_type_candidates": product_type_candidates or [],
            "snippets": grouped,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        normalized = re.sub(r"\s+", " ", text or "").strip()
        if not normalized:
            return []
        marked = re.sub(r"([.!?。！？])\s+", r"\1<SPLIT>", normalized)
        marked = re.sub(r"(다\.|요\.)\s+", r"\1<SPLIT>", marked)
        parts = marked.split("<SPLIT>")
        if len(parts) == 1:
            parts = re.split(r"(?<=[.!?])\s+|(?<=다)\s+", normalized)
        return [part.strip() for part in parts if part.strip()]
