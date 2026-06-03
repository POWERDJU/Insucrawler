# AGENTS.md

이 저장소에서 작업하는 Codex/개발자는 아래 규칙을 따른다.

- Python 3.11+를 기준으로 FastAPI, SQLAlchemy, Pydantic을 사용한다.
- API key, token, 실제 secret을 코드/문서/테스트에 하드코딩하지 않는다.
- `.env`는 커밋하지 않고 `.env.example`만 유지한다.
- 원문 기사 전문 저장은 기본 비활성화한다. `ENABLE_ARTICLE_BODY_FETCH=false`가 기본값이다.
- LLM은 수집을 담당하지 않는다. 뉴스 수집은 collector/fetcher가 담당하고 LLM은 추출, 검증, 충돌 판정에만 사용한다.
- `evidence_text` 없는 정형 추출값은 자동 확정 저장하지 않는다.
- 보험종류 확정 우선순위는 `manual > rule > LLM`이다.
- 회사명/업종 표준화는 `company_dictionary.csv`를 LLM보다 우선한다.
- 피벗에서 `include_secondary`는 반드시 `COUNT(DISTINCT product_id)` 의미로 집계한다.
- product grain, article grain, coverage grain, sales metric grain, LLM run grain을 혼동하지 않는다.
- grain이 다른 metric을 한 피벗에서 같이 볼 때는 중복 집계 방지 로직과 제한사항을 `docs/PIVOT_SPEC.md`에 반영한다.
- 테스트는 pytest로 작성하고, normalizer/classifier/schema/router/pivot/search의 회귀 테스트를 유지한다.
- schema/API/pivot 동작을 변경하면 관련 docs를 같이 업데이트한다.
