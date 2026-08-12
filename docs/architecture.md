# Architecture

## 경계

`src/search`는 검색 공급자, `src/collectors/public_web.py`는 원문 접근, `src/services/discovery`는 query plan·행동 추출·군집화·시장 구조 조사·논제 작성·보고를 담당합니다. 외부 경계와 결과는 모두 Pydantic으로 검증합니다. API/UI는 `output/<run_id>/portfolio.json`을 읽기만 하며 외부 검색을 시작하지 않습니다.

프로덕션 의존 방향은 `CLI → (선택적 SearchProvider 또는 raw verified URLs) → PublicWebCollector → PortfolioDiscoveryGraph → lane-aware extraction/clustering/thesis → reporting`입니다. Discovery는 `PROBLEM_SOLVER`, `BEHAVIOR_REDESIGN`, `WILD_BET` 세 레인으로 fan-out하며 최종 포트폴리오는 각각 최대 2/2/1개입니다. Brave는 선택 사항이며 `discover-from-urls`는 검색 API 키 없이 실제 원문을 GET합니다.

## 상태와 실행 이력

`DiscoveryPortfolio`는 모드, focus, 공급자, 기간, 모든 쿼리, 결과/원문/snippet/제외 집계, 후보, 노드 이벤트, 한계를 보존합니다. `candidate_quality_audits`에는 후보별 Evidence Gate, critique finding/history, 코드 arbitration, revision 전후 fingerprint, verification, 방문 노드와 최종 route를 보존합니다. `DiscoveryEvent`는 입출력 참조, 제안/실제 route, 이유, attempt, provider, schema validation과 시간을 기록합니다.

Quality 서브그래프는 실행 시작 시 `DiscoveryContract`를 상태에 고정합니다. Cold Critique와 Exit Challenger는 이전 critique 문맥을 전달하지 않는 fresh ephemeral Codex 호출이고, 코드 Arbitration이 검증 가능한 사실을 우선합니다. 같은 Codex 모델 세 번의 역할 분리는 교차 모델 검증이 아니므로 논쟁적·고위험 판단은 사람 승인 대상으로 남깁니다.

CLI 관측성은 Codex invocation마다 민감하지 않은 heartbeat만 stderr에 보냅니다. 실행 ID, 후보 ID, 노드, invocation ID, 상태와 경과 시간만 노출합니다. `REPORT_COMPLETE`는 보고서 작성 성공일 뿐이며, 후보 판정은 `VALIDATE_PROBLEM/VALIDATE_DELIGHT/WILD_BET/HOLD/REJECT`로 별도 저장합니다.

기존 단일 후보 `IdeaState`, SQLAlchemy 엔티티, LLM abstraction은 정책·확장 기반으로 남아 있지만 live portfolio 실행의 SSOT는 `DiscoveryPortfolio` JSON입니다. 실제 검색 결과는 DB fixture 경로와 섞이지 않습니다.

## 사실 경계

검색 결과 메타데이터와 snippet은 `SearchResult`, 원문 접근 결과는 `PublicDocument`입니다. 원문 fetch 성공, 안전 URL, 허용 content type, 충분한 본문 조건을 통과해야 `ORIGINAL_VERIFIED`가 됩니다. 추출된 행동은 Evidence이고, root problem·structural gap·wedge·asset·expansion은 inference 또는 hypothesis로 표시됩니다. Thesis Writer는 새 출처나 시장 숫자를 만들지 않습니다.

URL 입력에는 원문 주소, 제목, 출처 유형, 발견 검색어, 게시일만 허용한다. persona/root problem/wedge/asset/expansion/evaluation은 입력할 수 없으며 별도 원자 노드가 순서대로 생성한다.

## 보안과 운영

fetcher는 HTTP(S)만 허용하고 localhost, private/link-local/reserved IP와 unsafe redirect를 차단합니다. 응답 크기·content type·timeout·동시성을 제한합니다. 자동 로그인, 메시지, 결제, 사용자 연락, 우회 크롤링은 구현하지 않습니다.
