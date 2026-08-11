# Evidence Policy

- A: 실제 결제·구매·고용·구축 행동
- B: 반복 수작업 또는 구체적 시간 소비
- C: 구체적인 불만과 대안 탐색
- D: 희망·의견
- E: AI 추정

최종 후보에는 서로 독립적인 A~C `ORIGINAL_VERIFIED` 근거가 최소 2개 필요합니다. 동일 URL/원문은 한 번만 세며, URL·원문 excerpt·검색 공급자/도메인·게시일·접근일을 보존합니다. 검색 결과 snippet만 본 자료는 `SEARCH_SNIPPET_ONLY`로 집계하고 최종 근거로 승격하지 않습니다.

현재 독립성 key는 source host와 canonical original URL을 결합합니다. 동일 글의 mirror/인용을 완벽히 검출하지 못하므로 최종 검증 전 사람이 원문 계보를 확인해야 합니다. 게시일 미상과 접근 실패는 unknown입니다. 출처가 없는 숫자는 생성하지 않습니다.

테스트 fixture는 `tests/fixtures`에만 있고 `is_fixture=true`, `provider=test-fixture`, `.invalid` URL을 사용합니다. live graph는 이를 거부합니다.
