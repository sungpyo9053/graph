from src.domain.models.quality import DiscoveryContract
from src.domain.models.schemas import ValidationPlan
from src.domain.policies.validation import delight_validation_contract_failures


def _plan(**updates: object) -> ValidationPlan:
    values = {
        "hypothesis": "sustained use is driven by curiosity about the next result",
        "target_user": "10 existing practitioners",
        "method": "seven-day diary and referral attribution",
        "duration_days": 7,
        "success_criterion": "longitudinal contract",
        "failure_criterion": "any core loop threshold fails",
        "estimated_cost_usd": 100,
        "next_action_if_pass": "run a larger test",
        "next_action_if_fail": "discard the reframe",
        "cohort_size": 10,
        "observation_days": 7,
        "minimum_consistent_users": 4,
        "minimum_active_days": 5,
        "minimum_next_week_requests": 3,
        "minimum_unsolicited_shares": 2,
        "require_referred_user_arrival": True,
        "require_curiosity_driven_return_check": True,
    }
    values.update(updates)
    return ValidationPlan.model_validate(values)


def test_delight_validation_requires_longitudinal_replay_sharing_and_referral() -> None:
    assert delight_validation_contract_failures(_plan(), DiscoveryContract()) == []


def test_one_time_novelty_or_two_shares_cannot_pass_delight_validation() -> None:
    weak = _plan(
        minimum_consistent_users=2,
        minimum_active_days=1,
        minimum_next_week_requests=1,
        require_referred_user_arrival=False,
        require_curiosity_driven_return_check=False,
    )
    failures = delight_validation_contract_failures(weak, DiscoveryContract())
    assert "consistent_use_threshold" in failures
    assert "next_week_continuation_requests" in failures
    assert "referred_user_arrival" in failures
    assert "curiosity_driven_return" in failures


def test_unsolicited_share_is_distinct_from_prompted_or_combined_replay_metric() -> None:
    failures = delight_validation_contract_failures(
        _plan(minimum_unsolicited_shares=1), DiscoveryContract()
    )
    assert failures == ["unsolicited_shares"]
