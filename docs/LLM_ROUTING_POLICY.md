# LLM Routing Policy

기본 모드는 `gemini_extract_qwen_verify`이다.

지원 모드:

- `gemini_extract_qwen_verify`
- `qwen_extract_gemini_verify`
- `parallel_consensus`
- `qwen_first_cost_saver`
- `gemini_only`
- `qwen_only`

라우팅 설정은 `config/llm_routing_policy.yaml`과 `LLM_PIPELINE_MODE` 환경변수로 관리한다.

## qwen_first_cost_saver

Qwen으로 먼저 추출하고 다음 조건이면 Gemini 검증을 수행한다.

- confidence 낮음
- 판매실적 있음
- 최대보장금액 있음
- 출시년월 있음
- 보험종류 충돌 또는 review 필요

## Monitoring

모든 LLM 호출은 `fact_llm_run`에 task type, provider, model, prompt/schema version, input hash, output JSON, validation status, latency, token, cost estimate를 저장한다.
