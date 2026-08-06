"""Project identity: two values, and the four rules that admit a new one.

Identity is exactly two values, a distribution name and an import package name.
The projection swaps the pack's pair for the new project's pair, and it changes
nothing else.

Rules `R1` to `R4` live here, because each one is a statement about a name.
`R3` needs the standard library module list and `R5` and `R6` need the
filesystem, so the application layer supplies both. This module reads no
external fact of its own.

The four rules answer in two groups, and the split is deliberate. `R1` to `R3`
read the request alone, so `check_request` answers them before anything opens
the projection source. `R4` compares the request against the pack, so
`check_tokens` needs the identity of the pack and cannot answer earlier. This
order keeps an unreadable payload a permanent rejection, never an unexpected
failure.
"""

from dataclasses import dataclass
import keyword
import re

from guardrails_pack.bootstrap.domain.errors import refuse

__all__ = ["Identity", "check_request", "check_tokens", "derive_package", "substitutions"]

# The distribution name rule of the Python packaging specification. The router
# turns the same name into the console script of the new project.
DISTRIBUTION_PATTERN = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?$")
# The import package rule. It is stricter than `str.isidentifier`, because an
# import package of this pack is lower case and starts with a letter.
PACKAGE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
SEPARATORS = ("-", ".")


@dataclass(frozen=True, slots=True, kw_only=True)
class Identity:
    """The two identity values of one project."""

    project_name: str
    package: str


def derive_package(project_name: str) -> str:
    """The import package that a distribution name gives, by separator swap."""
    derived = project_name
    for separator in SEPARATORS:
        derived = derived.replace(separator, "_")
    return derived


def substitutions(pack: Identity, project: Identity) -> tuple[tuple[str, str], ...]:
    """The two token pairs that the projection swaps, longest token first.

    The pack tokens do not overlap, so order changes no result. The tuple keeps
    the order stable anyway, because a stable order makes a byte comparison of
    two projections meaningful.
    """
    pairs = (
        (pack.project_name, project.project_name),
        (pack.package, project.package),
    )
    return tuple(sorted(pairs, key=lambda pair: len(pair[0]), reverse=True))


def _check_names(project: Identity) -> None:
    """`R1` and `R2`: both names obey their own naming rule."""
    if DISTRIBUTION_PATTERN.fullmatch(project.project_name) is None:
        raise refuse(
            "R1",
            f"'{project.project_name}' is not a valid distribution name.",
            "The name becomes the distribution and the console script of the project.",
            "Use letters, digits, '-', '_' and '.', and start and end with a letter or a digit.",
        )
    if PACKAGE_PATTERN.fullmatch(project.package) is None:
        raise refuse(
            "R2",
            f"'{project.package}' is not a valid import package name.",
            "The name becomes the one directory under 'src/' and every import of the project.",
            "Pass --package with a lower-case name that starts with a letter.",
        )


def _check_reserved(project: Identity, reserved: frozenset[str]) -> None:
    """`R3`: the import package shadows no keyword and no standard library module."""
    if keyword.iskeyword(project.package):
        raise refuse(
            "R3",
            f"'{project.package}' is a Python keyword.",
            "A keyword cannot name a module, so the project would not import.",
            "Pass --package with another name.",
        )
    if project.package in reserved:
        raise refuse(
            "R3",
            f"'{project.package}' is a standard library module name.",
            "The project would shadow that module for every import in its own tree.",
            "Pass --package with another name.",
        )


def check_tokens(project: Identity, pack: Identity) -> None:
    """`R4`: neither new value equals a pack token.

    This is the one name rule that reads the pack, so a caller runs it after it
    has read the identity of the projection source, and never before.
    """
    tokens = {pack.project_name, pack.package}
    for value in (project.project_name, project.package):
        if value in tokens:
            raise refuse(
                "R4",
                f"'{value}' is a name of the pack itself.",
                "The projection swaps that token, so the new project would carry the pack name.",
                "Choose a name of your own product.",
            )


def check_request(project: Identity, reserved: frozenset[str]) -> None:
    """Run `R1` to `R3` over one requested identity. Raise on the first refusal.

    Every rule here reads the request alone, so all three answer before a caller
    opens the projection source.
    """
    _check_names(project)
    _check_reserved(project, reserved)
