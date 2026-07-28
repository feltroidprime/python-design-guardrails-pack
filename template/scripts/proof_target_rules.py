"""Close the catalog over public behaviors, contracts, and CrossHair targets."""

from collections.abc import Iterable

from scripts.proof_catalog import ProofCatalog, PropertySpec
from scripts.proof_discovery import (
    ContractLink,
    SourceTarget,
    discover_behavior_targets,
    discover_target,
)
from scripts.proof_guard_model import Violation, violation


def build_target_map(catalog: ProofCatalog) -> dict[str, SourceTarget]:
    targets = {target.target: target for target in discover_behavior_targets(catalog.policy)}
    declared = {
        name
        for property_spec in catalog.properties
        for name in (*property_spec.targets, *property_spec.oracles)
    }
    for name in declared - targets.keys():
        target = discover_target(catalog.policy.source_root, name)
        if target is not None:
            targets[name] = target
    return targets


def _contract_link_violations(
    catalog: ProofCatalog,
    target: SourceTarget,
    contract: ContractLink,
) -> list[Violation]:
    if contract.property_id is None:
        return [
            violation(
                contract.path,
                contract.line,
                "PROOF002",
                f"icontract.{contract.decorator} on '{target.target}' needs a literal "
                "description='PROPERTY[ID]: ...'.",
            )
        ]
    property_spec = catalog.by_id.get(contract.property_id)
    if property_spec is None:
        return [
            violation(
                contract.path,
                contract.line,
                "PROOF003",
                f"Contract on '{target.target}' references unknown property "
                f"'{contract.property_id}'.",
            )
        ]
    if target.target not in property_spec.targets:
        return [
            violation(
                contract.path,
                contract.line,
                "PROOF004",
                f"Contract '{contract.property_id}' is attached to '{target.target}', "
                "but proof.toml does not target that behavior.",
            )
        ]
    return []


def closure_violations(
    catalog: ProofCatalog,
    behavior_targets: Iterable[SourceTarget],
) -> list[Violation]:
    declared = catalog.target_ids
    exempted = {exemption.target for exemption in catalog.exemptions}
    violations: list[Violation] = []
    for target in behavior_targets:
        if target.target not in declared and target.target not in exempted:
            violations.append(
                violation(
                    target.path,
                    target.line,
                    "PROOF001",
                    f"Public core behavior '{target.target}' is neither owned by a property "
                    "nor explicitly exempted in proof.toml.",
                )
            )
        for contract in target.contracts:
            violations.extend(_contract_link_violations(catalog, target, contract))
    return violations


def _matching_contracts(
    property_spec: PropertySpec,
    target: SourceTarget,
) -> tuple[ContractLink, ...]:
    return tuple(
        contract
        for contract in target.contracts
        if contract.property_id == property_spec.property_id
    )


def _icontract_target_violations(
    property_spec: PropertySpec,
    target_name: str,
    target: SourceTarget,
) -> list[Violation]:
    if "icontract" not in property_spec.evidence:
        return []
    matching = _matching_contracts(property_spec, target)
    if not matching:
        return [
            violation(
                target.path,
                target.line,
                "PROOF006",
                f"Target '{target_name}' needs an icontract contract linked with "
                f"PROPERTY[{property_spec.property_id}].",
            )
        ]
    declared_oracles = set(property_spec.oracles)
    if any(contract.invoked_targets & declared_oracles for contract in matching):
        return []
    return [
        violation(
            target.path,
            target.line,
            "PROOF007",
            f"Contract '{property_spec.property_id}' must invoke an exact declared oracle: "
            f"{', '.join(sorted(declared_oracles))}.",
        )
    ]


def _symbolic_target_violations(
    property_spec: PropertySpec,
    target_name: str,
    target: SourceTarget,
) -> list[Violation]:
    symbol_is_executable = target.kind in {"function", "method"}
    if not symbol_is_executable or "icontract" not in property_spec.evidence:
        return []
    if "crosshair" in property_spec.evidence and target_name in property_spec.crosshair_targets:
        return []
    return [
        violation(
            target.path,
            target.line,
            "PROOF027",
            f"Pure contracted target '{target_name}' must be listed as CrossHair evidence for "
            f"'{property_spec.property_id}'.",
        )
    ]


def _declared_target_violations(
    catalog: ProofCatalog,
    property_spec: PropertySpec,
    target_map: dict[str, SourceTarget],
) -> list[Violation]:
    violations: list[Violation] = []
    for name in property_spec.targets:
        target = target_map.get(name)
        if target is None:
            violations.append(
                violation(
                    catalog.path,
                    1,
                    "PROOF005",
                    f"Property '{property_spec.property_id}' targets missing '{name}'.",
                )
            )
        else:
            violations.extend(_icontract_target_violations(property_spec, name, target))
            violations.extend(_symbolic_target_violations(property_spec, name, target))
    return violations


def _declared_oracle_violations(
    catalog: ProofCatalog,
    property_spec: PropertySpec,
    target_map: dict[str, SourceTarget],
) -> list[Violation]:
    return [
        violation(
            catalog.path,
            1,
            "PROOF008",
            f"Property '{property_spec.property_id}' declares missing oracle '{oracle}'.",
        )
        for oracle in property_spec.oracles
        if oracle not in target_map
    ]


def _crosshair_target_violations(
    property_spec: PropertySpec,
    target_map: dict[str, SourceTarget],
) -> list[Violation]:
    violations: list[Violation] = []
    for target_name in property_spec.crosshair_targets:
        target = target_map.get(target_name)
        if target is None or property_spec.property_id in target.property_ids:
            continue
        violations.append(
            violation(
                target.path,
                target.line,
                "PROOF009",
                f"CrossHair target '{target_name}' must carry the icontract for "
                f"'{property_spec.property_id}'.",
            )
        )
    return violations


def property_target_violations(
    catalog: ProofCatalog,
    target_map: dict[str, SourceTarget],
) -> list[Violation]:
    violations: list[Violation] = []
    for property_spec in catalog.properties:
        violations.extend(_declared_target_violations(catalog, property_spec, target_map))
        violations.extend(_declared_oracle_violations(catalog, property_spec, target_map))
        violations.extend(_crosshair_target_violations(property_spec, target_map))
    return violations
