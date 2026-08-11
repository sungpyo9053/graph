# Adding a Discovery Node

1. Behavior Collector, Pain Miner, Root Problem Analyst, Market Structure Analyst, Wedge Designer, Expansion Analyst, Cold Critique/Exit Challenger, Thesis Writer 중 기존 책임에 포함되는지 먼저 확인합니다. Product 단계의 별도 Contrarian 노드는 추가하지 않습니다.
2. `src/domain/models/discovery.py`에 Pydantic 입력/출력을 추가하고 원문 사실과 inference/hypothesis를 분리합니다.
3. node를 `PortfolioDiscoveryGraph.run`에 작게 추가하고 `_node`로 감싸 실행 이력을 남깁니다.
4. 결정 가능한 gate는 코드로 작성합니다. LLM을 쓸 때만 `LLMClient.generate_structured`를 주입하고 output schema와 prompt version을 추가합니다.
5. 검색 공급자는 `SearchProvider`, collector는 `DiscoveryCollector` protocol을 구현합니다. fixture는 production 패키지에 두지 않습니다.
6. 성공, 원문 실패, 근거 부족, 중복, network/provider 오류, 결정성 테스트를 추가합니다.
7. `summary.md`의 조사 범위 필드는 삭제하거나 숨기지 말고 이 문서와 graph design을 함께 갱신합니다.

Thesis Writer는 새로운 근거나 숫자를 만들 수 없습니다. 앱 코딩·배포·자동 연락 노드는 범위 밖입니다.
