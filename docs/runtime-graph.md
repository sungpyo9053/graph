# Runtime Graph (registered edges)

이 그림의 조건 라벨과 목적지는 설명용 복사본이 아니라 그래프 builder가 직접 사용하는 `src/graphs/routes.py::GRAPH_ROUTE_REGISTRY`와 일치한다. `tests/graph/test_registered_topology.py`가 registry의 source/destination node가 실제 compiled LangGraph에 존재하는지, 평가 fan-out/fan-in과 주요 back-edge를 검사한다.

```mermaid
flowchart TD
  subgraph PORT[Portfolio Graph]
    PS((START)) --> PQ[plan_queries] --> PC[collect_behavior_sources]
    PC --> PN[normalize_evidence] --> SG[SNS Discovery Subgraph]
    SG --> PB[detect_workarounds]
    PB --> PD[deduplicate_root_problems] --> PE{review_problem_evidence}
    PE -- COLLECT_MORE --> PR[refine_behavior_queries] --> PC
    PE -- HOLD --> PM[select_balanced_candidates · 2/2/1]
    PE -- ANALYZE --> PO[orchestrate_candidate_subgraphs]
    PO -->|fan-out candidate 1..N| CG
    CG -->|fan-in| PM --> SAVE[save_result] --> PEND((END))
  end

  subgraph SOCIAL[SNS Discovery Graph]
    SS((START)) --> SX[extract_social_behavior_memes]
    SX --> SC[inspect_social_comment_participation]
    SC --> SI[verify_social_accounts_and_platforms]
    SI -->|fan-out| SA1[evaluate pain removal]
    SI -->|fan-out| SA2[evaluate behavior gamification]
    SI -->|fan-out| SA3[evaluate share·competition·collection]
    SA1 --> SM[merge archetypes]
    SA2 --> SM
    SA3 --> SM
    SM --> SE((END / one-week validation path))
  end

  subgraph PROBLEM[Problem or Behavior Opportunity Graph]
    PGS((START)) --> PAIN[extract_pain] --> PERSONA[identify_persona]
    PERSONA --> LANE{candidate lane}
    LANE -- PROBLEM_SOLVER --> ROOT[analyze_root_problem]
    LANE -- BEHAVIOR_REDESIGN/WILD_BET --> REFRAME[analyze_behavior_opportunity]
    ROOT --> PGATE{review_problem_evidence}
    REFRAME --> PGATE
    PGATE --> PGEND((END))
  end

  subgraph CG[Candidate Graph]
    CS((START)) --> PG[Problem Graph]
    PG -- ANALYZE_MARKET_STRUCTURE --> PROD[Product Graph]
    PG -- HOLD/REJECT --> CEND((END))
    PROD -- DESIGN_VALIDATION --> VAL[Validation Graph]
    PROD -- HOLD/REJECT --> CEND
    VAL -- REVISE_WEDGE --> PROD
    VAL -- HOLD/REJECT --> CEND
    VAL -- APPROVE --> QUAL[Quality Graph]
    QUAL -- report_complete --> WRITE[write Thesis] --> CEND
    QUAL -- hold/reject/human_review/collect_more/extract_behavior/recluster --> CEND
  end

  subgraph PROD[Product Graph]
    PA[analyze_existing_alternatives] --> PS_GAP[analyze_structural_gap]
    PS_GAP --> PW[design_wedge_candidates]
    PW --> E1[evaluate_problem_strength]
    PW --> E2[evaluate_repetition]
    PW --> E3[evaluate_workaround_strength]
    PW --> E4[evaluate_structural_gap]
    PW --> E5[evaluate_wedge_simplicity]
    PW --> E6[evaluate_switching_feasibility]
    PW --> E7[evaluate_founder_fit]
    PW --> EA[evaluate_asset_accumulation] --> EX[evaluate_expansion_potential]
    E1 --> MERGE[merge_evaluations]
    E2 --> MERGE
    E3 --> MERGE
    E4 --> MERGE
    E5 --> MERGE
    E6 --> MERGE
    E7 --> MERGE
    EX --> MERGE
    MERGE --> SEL[select_wedge] --> CR{product_quality_gate · code}
    CR -- REVISE_WEDGE / once --> SIMPLIFY[simplify to one input · one output]
    SIMPLIFY --> E1
    SIMPLIFY --> E2
    SIMPLIFY --> E3
    SIMPLIFY --> E4
    SIMPLIFY --> E5
    SIMPLIFY --> E6
    SIMPLIFY --> E7
    SIMPLIFY --> EA
    CR -- DESIGN_VALIDATION/HOLD/REJECT --> PROD_END((END))
  end

  subgraph VAL[Validation Graph]
    VD[design_validation] --> VR{validation_contract_gate · code}
    VR -- APPROVE/HOLD/REJECT --> VAL_END((END))
  end

  subgraph QUAL[Quality Graph]
    QE{evidence_gate}
    QE -- cold_critique --> QC[cold_critique]
    QE -- collect_more/extract_behavior/hold/reject --> QEND((END))
    QC -- arbitrate --> QA{arbitrate}
    QC -- hold / NON_CONVERGING_LOOP --> QEND
    QA -- targeted_revision --> QR[targeted_revision]
    QA -- final_verify --> QV{final_verify}
    QA -- collect_more/extract_behavior/recluster/human_review/hold/reject --> QEND
    QR -- evidence_gate / changed --> QE
    QR -- hold / unchanged-or-limit --> QEND
    QV -- exit_challenger --> QX{exit_challenger}
    QV -- hold/reject --> QEND
    QX -- arbitrate / new-BLOCKING --> QA
    QX -- report_complete/hold --> QEND
  end
```

`arbitrate → targeted_revision` 안에서는 finding category가 `root_problem_analysis`, `market_research`, `wedge_design`, `asset_expansion_analysis` 중 정확한 원자 노드를 선택한다. 수정 결과가 달라졌을 때만 `evidence_gate`로 돌아가며, 같은 canonical blocking finding 반복 또는 무변경은 HOLD한다.
