from src.domain.models.schemas import RiskLevel

BLOCKED_TERMS = {"credential theft", "stolen account", "불법 처방", "무단 계정 탈취"}
HIGH_TERMS = {"medical diagnosis", "financial advice", "법률 판단", "의료 진단", "위치 추적"}
MEDIUM_TERMS = {
    "crawl",
    "scrape",
    "크롤링",
    "자동 메시지",
    "personal data",
    "개인정보",
    "copyright",
    "저작권",
}


def assess_risk(text: str) -> tuple[RiskLevel, list[str]]:
    normalized = text.lower()
    checks = (
        (RiskLevel.BLOCKED, BLOCKED_TERMS),
        (RiskLevel.HIGH, HIGH_TERMS),
        (RiskLevel.MEDIUM, MEDIUM_TERMS),
    )
    for level, terms in checks:
        matches = sorted(term for term in terms if term in normalized)
        if matches:
            return level, [f"감지된 위험 키워드: {', '.join(matches)}"]
    return RiskLevel.LOW, []
