"""Independent primitive-only reference model for repository capability application."""

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Literal

type ModelCapabilityStatus = Literal["ABSENT", "DRAFT", "ACTIVE", "RETIRED"]
type ExpectedApplyStatus = Literal[
    "applied",
    "already_applied",
    "stale_plan",
    "product_file_exists",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class PlanFacts:
    """Primitive facts from one inspected plan, supplied by the state-machine edge."""

    plan_id: str
    capability_name: str
    product_writes: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class RepositoryFacts:
    """Primitive facts observed from a repository after an external action."""

    declarations: tuple[tuple[str, str], ...]
    product_file_hashes: tuple[tuple[str, str], ...]
    derived_index_membership: tuple[str, ...]
    paths: tuple[str, ...]


def content_digest(content: bytes) -> str:
    """Return the model's independent SHA-256 representation of immutable bytes."""
    return f"sha256:{sha256(content).hexdigest()}"


@dataclass(slots=True, kw_only=True)
class RepositoryModel:
    """Reference state made only of the five protocol facts named by the specification."""

    package: str
    capability_status: dict[str, ModelCapabilityStatus] = field(default_factory=dict)
    declaration_state: dict[str, str] = field(default_factory=dict)
    product_file_hashes: dict[str, str] = field(default_factory=dict)
    derived_index_membership: frozenset[str] = field(default_factory=frozenset)
    applied_plan_ids: set[str] = field(default_factory=set)

    def is_product_path(self, path: str) -> bool:
        """Return whether one repository-relative path is user-owned product state."""
        return path.startswith(
            (
                f"src/{self.package}/modules/",
                "proof/modules/",
                "tests/modules/",
                "verification/modules/",
                "docs/product/",
            )
        )

    def expected_apply_status(
        self,
        plan: PlanFacts,
        *,
        plan_is_stale: bool,
    ) -> ExpectedApplyStatus:
        """Predict the one allowed apply outcome without consulting production code."""
        if plan_is_stale:
            return "stale_plan"
        if plan.plan_id in self.applied_plan_ids:
            return "already_applied"
        if any(path in self.product_file_hashes for path, _ in plan.product_writes):
            return "product_file_exists"
        return "applied"

    def record_apply(
        self,
        plan: PlanFacts,
        *,
        status: str,
        plan_is_stale: bool,
    ) -> None:
        """Advance only a successful first application, rejecting divergent outcomes."""
        expected = self.expected_apply_status(plan, plan_is_stale=plan_is_stale)
        if status != expected:
            raise AssertionError(f"apply {plan.plan_id} returned {status!r}; expected {expected!r}")
        if status != "applied":
            return
        if plan.plan_id in self.applied_plan_ids:
            raise AssertionError(f"successful plan {plan.plan_id} was applied twice")
        if any(path in self.product_file_hashes for path, _ in plan.product_writes):
            raise AssertionError(f"apply {plan.plan_id} overwrote an existing product file")
        self.applied_plan_ids.add(plan.plan_id)
        self.capability_status[plan.capability_name] = "DRAFT"
        self.declaration_state[plan.capability_name] = "draft"
        self.product_file_hashes.update(plan.product_writes)
        self.derived_index_membership = frozenset(
            name
            for name, status_value in self.capability_status.items()
            if status_value == "ACTIVE"
        )

    def record_manual_product_write(self, path: str, content: bytes) -> None:
        """Record a legitimate direct user edit without attributing it to apply."""
        if not self.is_product_path(path):
            raise AssertionError(f"manual product edit used non-product path {path!r}")
        self.product_file_hashes[path] = content_digest(content)

    def assert_invariants(self, facts: RepositoryFacts) -> None:
        """Reject every divergence from the independent model and declared roots."""
        declarations = _unique_mapping(facts.declarations, label="declarations")
        hashes = _unique_mapping(facts.product_file_hashes, label="product file hashes")
        if declarations != self.declaration_state:
            raise AssertionError(
                f"declaration state diverged: observed {declarations!r}; expected {self.declaration_state!r}"
            )
        if hashes != self.product_file_hashes:
            raise AssertionError(
                f"product bytes diverged: observed {hashes!r}; expected {self.product_file_hashes!r}"
            )
        expected_active = frozenset(
            name
            for name, status_value in self.capability_status.items()
            if status_value == "ACTIVE"
        )
        actual_active = frozenset(facts.derived_index_membership)
        if actual_active != expected_active or actual_active != self.derived_index_membership:
            raise AssertionError(
                "derived index diverged: "
                + f"observed {sorted(actual_active)!r}; expected {sorted(expected_active)!r}"
            )
        outside_allowed_roots = tuple(
            path for path in facts.paths if not self._is_allowed_path(path)
        )
        if outside_allowed_roots:
            raise AssertionError(f"paths outside allowed roots: {outside_allowed_roots!r}")

    def _is_allowed_path(self, path: str) -> bool:
        return self.is_product_path(path) or path.startswith(
            (
                ".repo/capabilities/",
                f"src/{self.package}/_generated/",
                "proof/_generated/",
            )
        )


def _unique_mapping(items: tuple[tuple[str, str], ...], *, label: str) -> dict[str, str]:
    mapping = dict(items)
    if len(mapping) != len(items):
        raise AssertionError(f"{label} contain duplicate paths or names")
    return mapping
