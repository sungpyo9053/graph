from prometheus_client import Counter, Histogram

GRAPH_RUNS = Counter("graph_runs_total", "Graph runs", ["status"])
NODE_RUNS = Counter("node_runs_total", "Node runs", ["node", "status"])
NODE_DURATION = Histogram("node_duration_ms", "Node duration in milliseconds", ["node"])
NODE_RETRY = Counter("node_retry_total", "Node retries", ["node"])
ROUTE_SELECTED = Counter("route_selected_total", "Selected routes", ["route"])
HUMAN_REVIEW = Counter("human_review_total", "Human reviews", ["decision"])
IDEA_REJECTED = Counter("idea_rejected_total", "Rejected ideas", ["reason"])
IDEA_VALIDATED = Counter("idea_validated_total", "Validated ideas")
LLM_CALLS = Counter("llm_calls_total", "LLM calls", ["model", "status"])
LLM_COST = Counter("estimated_llm_cost", "Estimated LLM cost in USD", ["model"])
SCHEMA_FAILURES = Counter("schema_validation_failures", "LLM schema validation failures", ["task"])
