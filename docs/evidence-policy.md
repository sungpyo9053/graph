# Evidence Policy

- A: 실제 결제·구매·고용·구축 행동
- B: 반복 수작업 또는 구체적 시간 소비
- C: 구체적인 불만과 대안 탐색
- D: 희망·의견
- E: AI 추정

최종 후보에는 서로 독립적인 A~C `ORIGINAL_VERIFIED` 근거가 최소 2개 필요합니다. 이때 원문 역할이 `FIRSTHAND_BEHAVIOR`이고 실제 행동 claim이 확인된 자료만 행동 근거로 셉니다. 동일 URL/원문은 한 번만 세며, URL·원문 excerpt·검색 공급자/도메인·게시일·접근일을 보존합니다. 검색 결과 snippet만 본 자료는 `SEARCH_SNIPPET_ONLY`로 집계하고 최종 근거로 승격하지 않습니다.

원문 역할은 다음처럼 분리합니다.

- `FIRSTHAND_BEHAVIOR`: 작성자가 자신이 실제 수행한 반복 행동과 우회 방법을 서술
- `PROCEDURAL_GUIDE`: 무엇을 해야 하는지 설명하는 절차·사용법 문서
- `OFFICIAL_PROCESS`: 사업자·기관이 정한 접수 양식, 정책, 공식 절차
- `SECONDARY_REPORT`: 다른 사람의 문제를 요약한 기사·조사 보고
- `UNCLASSIFIED`: 위 역할을 확인할 수 없음

절차 안내문과 공식 접수 문서는 기존 대안·시장 구조를 조사하는 자료로는 사용할 수 있지만, 사용자가 그 행동을 실제로 반복했다는 독립 근거로 세지 않습니다. 특히 안내문에 결제·비용 단어가 있다는 이유로 A등급을 부여하지 않습니다. A등급은 작성자 자신의 결제·구매·고용·구축 행동이 확인될 때만 가능합니다.

현재 독립성 key는 source host와 canonical original URL을 결합합니다. 동일 글의 mirror/인용을 완벽히 검출하지 못하므로 최종 검증 전 사람이 원문 계보를 확인해야 합니다. 게시일 미상과 접근 실패는 unknown입니다. 출처가 없는 숫자는 생성하지 않습니다.

결정적 한국어/영어 표현 규칙은 보수적인 1차 필터입니다. 생략된 주어, 인용문, 혼합형 후기처럼 문체가 모호한 자료는 `UNCLASSIFIED`로 빠질 수 있으며, 이는 강한 근거를 잘못 승인하는 것보다 의도된 보수적 실패입니다.

테스트 fixture는 `tests/fixtures`에만 있고 `is_fixture=true`, `provider=test-fixture`, `.invalid` URL을 사용합니다. live graph는 이를 거부합니다.
