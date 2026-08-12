from __future__ import annotations

from src.domain.models.quality import DiscoveryContract
from src.domain.models.schemas import ValidationPlan


def delight_validation_contract_failures(
    plan: ValidationPlan | None, contract: DiscoveryContract
) -> list[str]:
    """Return missing longitudinal delight checks; novelty alone never passes."""
    if plan is None:
        return ["validation_plan_missing"]
    requirements = {
        "cohort_size": plan.cohort_size == contract.delight_validation_cohort_size,
        "observation_days": (
            plan.observation_days == contract.delight_validation_observation_days
            and plan.duration_days >= contract.delight_validation_observation_days
        ),
        "consistent_use_threshold": (
            plan.minimum_consistent_users
            == contract.delight_validation_minimum_consistent_users
            and plan.minimum_active_days == contract.delight_validation_minimum_active_days
        ),
        "next_week_continuation_requests": (
            plan.minimum_next_week_requests
            == contract.delight_validation_minimum_next_week_requests
        ),
        "unsolicited_shares": (
            plan.minimum_unsolicited_shares
            == contract.delight_validation_minimum_unsolicited_shares
        ),
        "unrewarded_second_cycle_start": (
            plan.minimum_unrewarded_second_cycle_starts
            == contract.delight_validation_minimum_unrewarded_second_cycle_starts
        ),
        "referred_user_arrival": (
            not contract.delight_validation_requires_referred_arrival
            or plan.require_referred_user_arrival
        ),
        "curiosity_driven_return": (
            not contract.delight_validation_requires_curiosity_return_check
            or plan.require_curiosity_driven_return_check
        ),
    }
    return [name for name, passed in requirements.items() if not passed]
