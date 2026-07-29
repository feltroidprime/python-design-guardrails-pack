"""Pure repository-generation decisions."""

import icontract

from repoctl.modules.repository_generation.domain.intents import (
    CapabilityIntent,
    RepositorySnapshot,
)
from repoctl.modules.repository_generation.domain.ownership import (
    OwnershipPathError,
    RepositoryPathCandidate,
    classify_path,
)
from repoctl.modules.repository_generation.domain.plans import (
    CapabilityPlan,
    canonical_plan_bytes,
)
from repoctl.modules.repository_generation.domain.plans_planner import (
    PlanningOwnershipError,
    build_plan,
    candidate_targets,
    zone_is_writable,
)
from repoctl.modules.repository_generation.domain.specifications import (
    plan_repetition_is_identical,
)


def _planning_targets_are_writable(
    snapshot: RepositorySnapshot,
    intent: CapabilityIntent,
) -> bool:
    try:
        return all(
            zone_is_writable(
                classify_path(
                    RepositoryPathCandidate(value=target.value),
                    snapshot.ownership_zones,
                )
            )
            for target in candidate_targets(snapshot, intent)
        )
    except OwnershipPathError:
        return False


def _planning_ownership_error(
    snapshot: RepositorySnapshot,
    intent: CapabilityIntent,
) -> PlanningOwnershipError:
    message = (
        "Every intended plan target must have one writable declared owner; "
        + f"snapshot package={snapshot.package}, intent={intent.name}."
    )
    return PlanningOwnershipError(message)


def _plan_is_deterministic(
    snapshot: RepositorySnapshot,
    intent: CapabilityIntent,
    result: CapabilityPlan,
) -> bool:
    repeated = build_plan(snapshot, intent)
    return plan_repetition_is_identical(
        canonical_plan_bytes(result),
        canonical_plan_bytes(repeated),
        result.plan_id,
        repeated.plan_id,
    )


@icontract.require(
    _planning_targets_are_writable,
    description="all intended targets have one writable declared owner",
    error=_planning_ownership_error,
)
@icontract.ensure(
    _plan_is_deterministic,
    description="PROPERTY[REPOCTL::PLAN-DETERMINISTIC]",
)
def plan(
    snapshot: RepositorySnapshot,
    intent: CapabilityIntent,
) -> CapabilityPlan:
    """Return every intended structural write from explicit immutable input."""
    return build_plan(snapshot, intent)
