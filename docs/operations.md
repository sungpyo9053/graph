# Operations

1. `.env`에 `BRAVE_SEARCH_API_KEY`와 조사 국가/언어/기간/원문 budget을 설정합니다.
2. `make discover MODE=open` 또는 `make discover MODE=focused FOCUS="..."`를 운영자가 명시적으로 실행합니다.
3. `summary.md`에서 검색 쿼리, 기간, result 수, 실제 검증 원문, snippet-only, 제외 사유를 먼저 확인합니다.
4. 후보 원문 링크를 사람이 재검토한 뒤 인터뷰나 concierge test를 수행합니다.

Brave 검색 API는 `X-Subscription-Token` 헤더를 사용합니다. 키는 출력이나 로그에 기록하지 않습니다. API 오류는 인증, quota/rate-limit, transient network/server, permanent request/response로 분류합니다. 키가 없으면 live 명령은 exit code 2로 실패하고 테스트 fixture를 실행하지 않습니다.

원문 접근은 공개 페이지에 한정되며 robots/약관/저작권/개인정보/재판매 조건은 운영자가 별도로 검토해야 합니다. 이 구현은 로그인을 우회하거나 차단을 회피하지 않습니다. 의료·금융·법률 판단, 위치정보, 자동 메시지, 계정 인증정보가 사업 전제이면 사람의 별도 위험 검토가 필요합니다.

운영 KPI는 후보 개수가 아니라 독립 강한 근거를 가진 문제 수, workaround 확인률, 원문 검증률, 인터뷰 확인률, 행동 변화율, 반복 기각 사유, 출처별 유효 발견률입니다.
