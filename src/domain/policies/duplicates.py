import math
import re
from dataclasses import dataclass
from typing import Protocol

from src.domain.models.schemas import WedgeCandidate

TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")

SEMANTIC_PATTERNS: dict[str, tuple[tuple[str, str], ...]] = {
    "behavior_verbs": (
        (r"전화|문의", "phone_contact"),
        (r"확인|조회|체크|살피", "check"),
        (r"기록|입력|정리", "record"),
        (r"보내|전송|제출", "send"),
        (r"비교|대조", "compare"),
    ),
    "target_objects": (
        (r"약국", "pharmacy"),
        (r"재고|품절", "inventory"),
        (r"처방", "prescription"),
        (r"가격|견적", "price_quote"),
        (r"예약|취소표", "reservation"),
        (r"문서|서류", "document"),
    ),
    "workaround_types": (
        (r"전화|문의", "phone"),
        (r"엑셀|스프레드시트", "spreadsheet"),
        (r"카톡|메시지|문자", "messaging"),
        (r"수기|수작업|직접", "manual"),
    ),
    "solution_archetypes": (
        (r"알림|통지", "alert"),
        (r"비교|대조", "comparison"),
        (r"기록|이력", "record"),
        (r"연결|매칭", "matching"),
        (r"결과|판정|리포트", "single_result"),
    ),
}


@dataclass(frozen=True)
class BehaviorSolutionSignature:
    behavior_verbs: frozenset[str]
    target_objects: frozenset[str]
    workaround_types: frozenset[str]
    wedge_input: frozenset[str]
    wedge_output: frozenset[str]
    solution_archetypes: frozenset[str]


class EmbeddingAdapter(Protocol):
    def embed(self, text: str) -> list[float]: ...


class DeterministicTokenEmbedding:
    dimensions = 64

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in tokens(text):
            vector[sum(token.encode("utf-8")) % self.dimensions] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


def tokens(text: str) -> set[str]:
    return {part.lower() for part in TOKEN_RE.findall(text) if len(part) > 1}


def jaccard(left: str, right: str) -> float:
    a, b = tokens(left), tokens(right)
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b) if a | b else 0.0


def behavior_solution_signature(
    *,
    repeated_behavior: str,
    workaround: str,
    wedge_input: str,
    wedge_output: str,
    solution_archetype: str,
) -> BehaviorSolutionSignature:
    behavior_text = f"{repeated_behavior} {workaround}"
    return BehaviorSolutionSignature(
        behavior_verbs=_semantic_values("behavior_verbs", behavior_text),
        target_objects=_semantic_values("target_objects", behavior_text),
        workaround_types=_semantic_values("workaround_types", workaround),
        wedge_input=frozenset(tokens(wedge_input)),
        wedge_output=frozenset(tokens(wedge_output)),
        solution_archetypes=_semantic_values(
            "solution_archetypes", f"{solution_archetype} {wedge_output}"
        ),
    )


def same_behavior_solution_archetype(
    left: BehaviorSolutionSignature, right: BehaviorSolutionSignature
) -> bool:
    behavior_same = (
        bool(left.behavior_verbs & right.behavior_verbs)
        and bool(left.target_objects & right.target_objects)
        and bool(left.workaround_types & right.workaround_types)
    )
    input_same = _set_jaccard(left.wedge_input, right.wedge_input) >= 0.5
    output_same = _set_jaccard(left.wedge_output, right.wedge_output) >= 0.5
    archetype_same = bool(left.solution_archetypes & right.solution_archetypes)
    return behavior_same and archetype_same and (input_same or output_same)


def _semantic_values(dimension: str, text: str) -> frozenset[str]:
    return frozenset(
        canonical
        for pattern, canonical in SEMANTIC_PATTERNS[dimension]
        if re.search(pattern, text, re.IGNORECASE)
    )


def _set_jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right) if left | right else 0.0


def problem_similarity(left: dict[str, str], right: dict[str, str]) -> float:
    fields = (
        "persona",
        "situation",
        "repeated_behavior",
        "pain",
        "current_workaround",
        "root_problem",
    )
    return sum(jaccard(left.get(field, ""), right.get(field, "")) for field in fields) / len(fields)


def wedge_similarity(left: WedgeCandidate, right: WedgeCandidate) -> float:
    fields = ("target_user", "user_input", "core_process", "expected_output", "switching_reason")
    return sum(jaccard(getattr(left, field), getattr(right, field)) for field in fields) / len(
        fields
    )


def duplicate_groups(texts: list[str], threshold: float = 0.82) -> list[list[int]]:
    groups: list[list[int]] = []
    assigned: set[int] = set()
    for index, item in enumerate(texts):
        if index in assigned:
            continue
        group = [index]
        for other in range(index + 1, len(texts)):
            if other not in assigned and jaccard(item, texts[other]) >= threshold:
                group.append(other)
                assigned.add(other)
        groups.append(group)
    return groups
