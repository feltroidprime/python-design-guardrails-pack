"""Require independent, pure, boolean property oracles."""

from scripts.proof_catalog import ProofCatalog, PropertySpec
from scripts.proof_discovery import OracleShape, discover_oracle
from scripts.proof_guard_model import Violation, simple_name, violation

EFFECTFUL_ORACLE_MODULE_ROOTS = frozenset(
    {
        "aiohttp",
        "asyncio",
        "boto3",
        "httpx",
        "logging",
        "multiprocessing",
        "os",
        "pandas",
        "pathlib",
        "polars",
        "psycopg",
        "pymongo",
        "random",
        "redis",
        "requests",
        "secrets",
        "shutil",
        "socket",
        "sqlite3",
        "subprocess",
        "sys",
        "tempfile",
        "threading",
        "time",
        "urllib",
        "uuid",
    }
)
EFFECTFUL_ORACLE_CALL_NAMES = frozenset(
    {
        "__import__",
        "breakpoint",
        "compile",
        "eval",
        "exec",
        "exists",
        "glob",
        "input",
        "is_dir",
        "is_file",
        "iterdir",
        "mkdir",
        "now",
        "open",
        "perf_counter",
        "print",
        "read_bytes",
        "read_text",
        "rename",
        "resolve",
        "rglob",
        "rmdir",
        "sleep",
        "stat",
        "system",
        "time",
        "today",
        "unlink",
        "utcnow",
        "uuid1",
        "uuid4",
        "write_bytes",
        "write_text",
    }
)


def _basic_oracle_shape_defects(oracle: OracleShape) -> tuple[str, ...]:
    checks = (
        (oracle.is_async, "is async"),
        (oracle.return_annotation != "bool", "does not declare -> bool"),
        (oracle.has_variadic_parameters, "uses variadic parameters"),
        (
            bool(oracle.forbidden_nodes),
            "contains " + ", ".join(sorted(oracle.forbidden_nodes)),
        ),
    )
    return tuple(message for failed, message in checks if failed)


def _effectful_oracle_imports(oracle: OracleShape) -> tuple[str, ...]:
    return tuple(
        sorted(
            module
            for module in oracle.imported_modules
            if module.partition(".")[0] in EFFECTFUL_ORACLE_MODULE_ROOTS
        )
    )


def _effectful_oracle_calls(oracle: OracleShape) -> tuple[str, ...]:
    return tuple(
        sorted(
            called_name
            for called_name in oracle.called_names
            if called_name.rpartition(".")[2] in EFFECTFUL_ORACLE_CALL_NAMES
            or ".random." in called_name
        )
    )


def _effect_defect(label: str, values: tuple[str, ...]) -> tuple[str, ...]:
    return (f"{label}: {', '.join(values)}",) if values else ()


def _oracle_shape_defects(oracle: OracleShape) -> tuple[str, ...]:
    return (
        *_basic_oracle_shape_defects(oracle),
        *_effect_defect(
            "imports effectful module(s)",
            _effectful_oracle_imports(oracle),
        ),
        *_effect_defect(
            "calls effectful operation(s)",
            _effectful_oracle_calls(oracle),
        ),
    )


def _implementation_imports(
    catalog: ProofCatalog,
    oracle: OracleShape,
) -> tuple[str, ...]:
    project_roots = {module.partition(".")[0] for module in catalog.policy.behavior_roots}
    return tuple(
        sorted(
            module
            for module in oracle.imported_modules
            if module.partition(".")[0] in project_roots
            and module.rpartition(".")[2] not in catalog.policy.oracle_module_stems
        )
    )


def _called_target_names(
    property_spec: PropertySpec,
    oracle: OracleShape,
) -> tuple[str, ...]:
    targets = {simple_name(target) for target in property_spec.targets}
    calls = {called_name.rpartition(".")[2] for called_name in oracle.called_names}
    return tuple(sorted(targets & calls))


def _oracle_location_violation(
    catalog: ProofCatalog,
    oracle_name: str,
    oracle: OracleShape,
) -> list[Violation]:
    allowed = catalog.policy.oracle_module_stems
    if oracle.module_stem in allowed:
        return []
    return [
        violation(
            oracle.path,
            oracle.line,
            "PROOF022",
            f"Oracle '{oracle_name}' must live in one of the configured specification modules: "
            f"{', '.join(sorted(allowed))}.",
        )
    ]


def _oracle_shape_violation(
    oracle_name: str,
    oracle: OracleShape,
) -> list[Violation]:
    defects = _oracle_shape_defects(oracle)
    if not defects:
        return []
    return [
        violation(
            oracle.path,
            oracle.line,
            "PROOF023",
            f"Oracle '{oracle_name}' must be a total synchronous predicate over explicit inputs; "
            f"it {'; '.join(defects)}.",
        )
    ]


def _oracle_import_violation(
    catalog: ProofCatalog,
    oracle_name: str,
    oracle: OracleShape,
) -> list[Violation]:
    imports = _implementation_imports(catalog, oracle)
    if not imports:
        return []
    return [
        violation(
            oracle.path,
            oracle.line,
            "PROOF024",
            f"Oracle '{oracle_name}' imports implementation modules ({', '.join(imports)}); "
            "specifications must compare explicit facts without importing production behavior.",
        )
    ]


def _oracle_call_violation(
    property_spec: PropertySpec,
    oracle_name: str,
    oracle: OracleShape,
) -> list[Violation]:
    called = _called_target_names(property_spec, oracle)
    if not called:
        return []
    return [
        violation(
            oracle.path,
            oracle.line,
            "PROOF025",
            f"Oracle '{oracle_name}' calls the behavior it judges: {', '.join(called)}.",
        )
    ]


def _one_oracle_violations(
    catalog: ProofCatalog,
    property_spec: PropertySpec,
    oracle_name: str,
) -> list[Violation]:
    oracle = discover_oracle(catalog.policy.source_root, oracle_name)
    if oracle is None:
        return []
    return [
        *_oracle_location_violation(catalog, oracle_name, oracle),
        *_oracle_shape_violation(oracle_name, oracle),
        *_oracle_import_violation(catalog, oracle_name, oracle),
        *_oracle_call_violation(property_spec, oracle_name, oracle),
    ]


def oracle_violations(catalog: ProofCatalog) -> list[Violation]:
    return [
        violation
        for property_spec in catalog.properties
        for oracle_name in property_spec.oracles
        for violation in _one_oracle_violations(catalog, property_spec, oracle_name)
    ]
