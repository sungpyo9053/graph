# Native Graph Inspector

`make gui`는 PySide6 기반 데스크톱 실행 관찰기다. MFC 같은 독립 창에서
LangGraph의 실제 실행 순서가 BFS/A* 시각화처럼 확장되는 모습을 보여주되,
탐색 알고리즘을 흉내 낸 애니메이션은 아니다.

## 데이터 흐름

```text
PortfolioDiscoveryGraph / candidate subgraphs
        │
        ├─ code node trace ───────┐
        └─ Codex heartbeat ───────┤
                                  ▼
                         runtime observer
                                  │ Qt Signal
                                  ▼
                           QGraphicsScene
                    node state + traversed edge
```

UI worker는 기존 `VerifiedUrlCollector`, `PublicPageFetcher`,
`PortfolioDiscoveryGraph`, `write_portfolio`를 직접 재사용한다. 별도의 간이
그래프나 fake 결과 생성기는 없다. 실행은 한 번 시작해 종료되며 내부 무한
스케줄러도 없다.

화면 topology도 수동 `NODES`/`EDGES` 정의를 SSOT로 사용하지 않는다. 실제
runtime builder들을 실행 없이 compile하고 각 `get_graph().nodes`와
`get_graph().edges`에서 qualified display topology를 생성한다. topology 전용
collector와 LLM은 호출되면 즉시 실패하므로 fixture나 fake 판단을 만들지 않는다.
회귀 테스트는 각 compiled graph의 전체 node 집합과 `(source, target, route,
conditional)` edge 집합이 GUI snapshot과 정확히 같은지 검사한다.

## 시각 상태

- `IDLE`: 아직 방문하지 않은 노드
- `RUNNING`: Codex 호출 또는 실행 중인 노드, pulse 애니메이션
- `COMPLETED`: 정상 종료
- `REVISED`: 수정·재수집·재군집 경로를 선택한 노드
- `FAILED`: 실패 또는 기각

실선은 일반 edge, 점선은 compiled graph가 `conditional=True`로 보고한 edge다.

노드 간 실제 관찰된 이동은 파란 edge, back-edge와 수정 이동은 주황 edge로
강조한다. Candidate별 마지막 노드를 따로 기억하므로 fan-out된 후보 실행이
서로의 경로를 잘못 연결하지 않는다.

## 실행과 점검

```bash
.venv/bin/pip install -e '.[gui]'
LLM_PROVIDER=codex make gui
QT_QPA_PLATFORM=offscreen .venv/bin/python -m src.desktop --smoke-test
QT_QPA_PLATFORM=offscreen .venv/bin/python -m src.desktop \
  --screenshot /tmp/idea-graph-inspector.png
```

`--smoke-test`와 `--screenshot`은 그래프 자체를 실행하지 않으며 창 구성과
렌더링만 검사한다. 실제 탐색은 GUI의 **아이디어 찾기** 버튼으로 명시적으로
시작한다.

## 독립 실행 앱 빌드

```bash
.venv/bin/pip install -e '.[gui,package]'
make gui-build
open 'dist/Idea Discovery Graph.app'
```

PyInstaller spec은 `config/`와 결론 힌트가 없는 `verified-urls.json`만 data로
포함한다. `.env`, `output/`, `.codex/`, 인증 파일과 과거 실행 결과는 번들에
넣지 않는다. 앱은 Finder의 제한된 PATH를 보완하기 위해 일반적인 사용자 실행
경로만 추가하며 `auth.json`을 직접 읽지 않는다.

이 빌드는 동일한 macOS 머신에서 바로 실행할 수 있는 앱이다. 다른 Mac에
배포할 때 Gatekeeper 경고 없이 실행하려면 Apple Developer ID 서명과
notarization이 별도로 필요하다. Windows `.exe`는 Windows 환경에서 같은 spec을
빌드해야 한다.

## 보안 경계

타임라인에는 식별자와 실행 상태만 표시한다. 런타임 이벤트 내부에 요약 detail이
있더라도 UI는 이를 출력하지 않는다. Codex 인증 파일을 읽거나 표시하지 않고,
LLM 호출은 기존 read-only Codex 어댑터의 보안 경계를 그대로 사용한다.
