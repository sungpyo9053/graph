# Evidence Thesis Graph

공개 웹에서 실제 반복 행동과 우회 행동을 찾고, 근본 문제·기존 대안·구조적 공백·가장 작은 진입 해결책·축적 자산·확장 경로를 연결하는 아이디어 발굴 그래프입니다. 발견한 앱이나 웹을 개발·배포하지 않습니다. 산출물은 근거 범위가 명시된 **Problem–Wedge–Expansion Thesis** Markdown/JSON입니다.

실행 구조는 `최상위 Discovery 오케스트레이터 → 후보별 Problem/Product/Validation/Quality 서브그래프 → 원자 에이전트 노드`입니다. Quality Graph는 `Evidence Gate → Cold Critique → Code Arbitration → Targeted Revision → Final Verify → Exit Challenger`를 반복하고, 모든 계약을 통과한 뒤에만 Thesis를 씁니다. [등록 edge 기반 Runtime Graph](docs/runtime-graph.md)와 [상세 설계](docs/graph-design.md)를 참고하십시오.

정량 가능한 근거 수, 중복도, 점수 합산, 필수 필드와 실행 한도는 코드가 판정합니다. 근본 문제, 구조적 공백, 웨지, 자산-확장 인과, 반증처럼 의미 판단이 필요한 작업만 구조화된 LLM을 호출합니다. 운영에서 GPT를 사용하려면 다음을 설정합니다.

```dotenv
LLM_PROVIDER=openai
OPENAI_API_KEY=replace-with-api-key
OPENAI_MODEL=gpt-5-mini
```

테스트는 외부 키 없이 `LLM_PROVIDER=fake`로 결정적으로 실행됩니다.

현재 로그인된 Codex CLI 인증을 재사용하려면 다음처럼 실행합니다. `auth.json`은 읽거나 복사하지 않으며, 각 노드는 비 Git 임시 디렉터리에서 `--skip-git-repo-check`, `--sandbox read-only`, `--output-schema`, 임시 `-o` 파일을 사용합니다. 비 Git 임시 디렉터리이기 때문에 `--skip-git-repo-check`가 필요하며 이 이유는 호출 감사 로그에 기록됩니다.

```bash
codex login status
codex --version
LLM_PROVIDER=codex CODEX_MAX_CONCURRENCY=1 \
  make discover-from-urls INPUT=verified-urls.json
```

`CODEX_MAX_CONCURRENCY`는 기본 1이고 최대 2입니다. Codex 출력은 노드별 JSON Schema와 Pydantic으로 이중 검증하며 한 번만 재시도합니다. 계속 실패하면 fake로 대체하지 않고 실행을 실패시킵니다. 각 감사 레코드에는 실제 provider/model, node, exit code, duration, schema 결과, retry, ephemeral/read-only 여부와 이전 critique 포함 여부가 남습니다.

장기 Codex 호출은 기본 15초마다 stderr에 heartbeat를 표시합니다. `CODEX_HEARTBEAT_SECONDS`로 1~60초 사이에서 조정할 수 있습니다. heartbeat에는 `시간`, `run_id`, `candidate_id`, `node`, `invocation_id`, `STARTED/RUNNING/COMPLETED/FAILED`, `elapsed_seconds`만 포함하며 원문·prompt·모델 응답·인증정보는 출력하지 않습니다.

아이디어 생성·Cold Critique·Exit Challenger는 같은 Codex 모델이므로 독립적인 교차 모델 검증이 아닙니다. fresh/ephemeral 세션은 문맥 오염만 줄입니다. 운영 책임은 `Codex의 비판 제안 → 코드 Gate의 확인 가능한 사실 판정 → 사람의 논쟁적·고위험 승인`으로 분리합니다.

결과는 “전체 시장의 절대 상위 5개”가 아닙니다. **해당 실행의 검색 쿼리·출처·조사 기간·접근 가능한 원문 범위에서의 근거 기반 상위 후보 최대 5개**입니다. 독립적인 원문 A~C 근거가 2개 미만이면 후보를 억지로 채우지 않습니다.

`VALIDATE`는 아이디어나 시장이 검증됐다는 뜻이 아니라, Wedge 행동 실험을 실행할 가치가 있다는 판정입니다. 전환 행동·결제 의향·반복 사용·축적 자산·확장이 미검증인 상태는 validation hypothesis로 보존하며 그 사실만으로 HOLD하지 않습니다. HOLD는 현재 데이터 접근 불가, 외부 참여 없이는 최초 가치가 없음, 치명적 위험 또는 비수렴처럼 당장 해결할 수 없는 차단에 사용합니다.

LLM 사용량은 단계적으로 제한합니다. 코드가 원문 행동 추출·중복 제거·근거 Gate를 수행하고, 근거순 상위 문제군 최대 10개만 Root/Market/Wedge 분석을 거칩니다. 그중 코드 예비 순위와 다양성 Gate 상위 5개만 Validation/Cold Critique로 이동하며, Cold를 통과한 후보만 Exit Challenger를 호출합니다.

## 설치

Python 3.12가 필요합니다.

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
cp .env.example .env
```

## 무료 verified-URL 실행

Brave 키 없이도 Codex나 운영자가 공개 웹에서 확인한 원문 10~30개를 실행할 수 있습니다. 각 URL 항목에는 아래 다섯 필드만 허용됩니다. persona, root problem, wedge, asset, expansion, 평가는 입력하면 검증 오류가 발생합니다.

```json
{
  "url": "https://example.org/original",
  "title": "원문 제목",
  "source_type": "community",
  "discovered_via_query": "반복 수작업 우회 행동",
  "published_at": "2026-01-01T00:00:00Z"
}
```

```bash
make discover-from-urls INPUT=verified-urls.json
```

## 선택적 Brave live 검색 설정

자동 검색용 어댑터는 Brave Search API입니다. 사용하려는 경우에만 키를 설정합니다. `discover-from-urls`에는 필요하지 않습니다.

```dotenv
SEARCH_PROVIDER=brave
BRAVE_SEARCH_API_KEY=replace-with-your-key
DISCOVERY_COUNTRY=US
DISCOVERY_SEARCH_LANG=en
DISCOVERY_LOOKBACK_DAYS=730
DISCOVERY_RESULTS_PER_QUERY=10
DISCOVERY_MAX_ORIGINAL_PAGES=80
DISCOVERY_OUTPUT_DIR=output
```

`BRAVE_SEARCH_API_KEY`가 없으면 `make discover`와 `make discover-daily`만 실패하며 fixture로 대체 실행하지 않습니다. 무료 `make discover-from-urls`는 계속 동작합니다. 검색 결과를 저장·재사용할 경우 각 원문의 약관·저작권을 운영자가 확인해야 합니다.

## 실행

전체 시장의 여러 문제 영역을 탐색합니다.

```bash
make discover MODE=open
```

특정 주제를 네 가지 문제 렌즈로 탐색합니다.

```bash
make discover MODE=focused FOCUS="dental clinic operations"
```

세부 옵션은 다음과 같이 직접 전달할 수 있습니다.

```bash
.venv/bin/python -m src.cli discover --mode open \
  --country US --search-lang en --lookback-days 730 \
  --results-per-query 10 --max-original-pages 80 --max-candidates 5
```

각 실행은 `output/<run_id>/`에 다음을 생성합니다.

- `summary.md`: 모드, 문제 영역, 모든 쿼리, 조사 기간, 검색 결과 수, 원문 접근/검증 수, snippet-only 수, 제외 이유, 후보 수, 조사 한계
- `portfolio.json`: 검색 범위, 전체 GraphRun 이벤트, 후보별 quality audit와 구조화된 전체 논제
- `source-audit.json`: URL별 `ORIGINAL_VERIFIED`/`SEARCH_SNIPPET_ONLY`, 접근 시각과 실패 이유
- `candidate-N.md`: 정확한 20개 섹션의 Problem–Wedge–Expansion Thesis

검색 snippet만 본 자료는 `SEARCH_SNIPPET_ONLY`, 실제 URL을 가져와 본문을 파싱한 자료는 `ORIGINAL_VERIFIED`입니다. 최종 A~C 행동 근거에는 원문 GET에 성공했을 뿐 아니라 작성자 자신의 수행 경험으로 분류된 `FIRSTHAND_BEHAVIOR`만 들어갑니다. 절차 안내(`PROCEDURAL_GUIDE`)와 공식 접수 규정(`OFFICIAL_PROCESS`)은 대안 조사에는 쓰지만 행동 근거 수를 늘리지 않습니다.

## 결과 조회 UI/API

```bash
.venv/bin/uvicorn src.main:app --reload
```

브라우저에서 `http://127.0.0.1:8000`을 엽니다. UI는 저장된 결과와 실행 경로만 조회하며 검색이나 외부 행동을 자동 실행하지 않습니다.

- `GET /api/v1/discoveries`
- `GET /api/v1/discoveries/{run_id}`
- `GET /api/v1/runs/{run_id}/graph`
- `GET /api/v1/reports/{run_id}`
- `GET /api/v1/health`

## 테스트

```bash
make test
make lint
make typecheck
```

테스트 fixture는 `tests/fixtures/`와 `tests/fixture_collector.py`에만 있습니다. production graph는 fixture collector를 거부하고, 테스트가 `allow_test_fixture=True`를 명시한 경우에만 허용합니다. 인터넷과 API 키 없이도 어댑터 HTTP 계약, 원문/snippet 분리, 근거 gate, 미충원, 결정성, 결과 API를 검증합니다.

LLM 추상화는 기존 `LLMClient.generate_structured`와 fake/OpenAI 호환 구현으로 유지되지만, 현재 live 검색/근거 추출의 코드 gate는 LLM 키 없이 동작합니다. 비밀키는 코드·fixture·결과 파일에 넣지 마십시오.

세부 설계는 [architecture](docs/architecture.md), [graph design](docs/graph-design.md), [evidence policy](docs/evidence-policy.md), [scoring rubric](docs/scoring-rubric.md), [operations](docs/operations.md), [adding an agent](docs/adding-an-agent.md)을 참고하십시오.

## 공개 저장소 범위와 현재 한계

저장소에는 그래프 코드, 설정, 문서, 테스트 전용 fixture와 결론 힌트가 없는 URL 메타데이터 예시만 포함합니다. `.env`, `.codex/`, `auth.json`, `output/`, stdout/stderr 실행 로그와 로컬 DB는 공개 대상에서 제외합니다. 원문 본문 복제물과 Codex 인증정보도 저장하지 않습니다.

Product Contrarian 제거 후의 정책 재평가는 [policy re-evaluation](docs/policy-reevaluation.md)에 기록했습니다. 사용자 지시에 따라 기존 원문과 기존 구조화 응답만 사용했고 새 검색·새 LLM 호출은 하지 않았습니다. 따라서 최신 정책으로 생성된 실제 후보가 있다는 뜻은 아닙니다.

현재 제한은 다음과 같습니다.

- Codex 생성·Cold Critique·Exit Challenger가 같은 모델이므로 교차 모델 검증이 아닙니다.
- 자동 live 검색은 선택적 Brave 어댑터에 키가 필요하지만, verified URL 경로는 키 없이 실행됩니다.
- 공개 웹 원문 접근·저장·재사용의 약관과 저작권 판단은 운영자 책임입니다.
- `VALIDATE`는 시장 검증 완료가 아니라 수동 행동 실험을 실행할 가치가 있다는 판정입니다.
- Product Gate 정책 변경 뒤 실제 live 전체 그래프는 새로 실행하지 않았습니다.
- 테스트에는 FastAPI `TestClient`의 `httpx` 연동 deprecation 경고 1건이 남아 있으며 기능 실패는 아닙니다.
