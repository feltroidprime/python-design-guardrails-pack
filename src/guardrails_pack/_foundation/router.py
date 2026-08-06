"""The pack-owned command seam: one command line derived from composition.

The router imports exactly one user-owned module, the composition root, and it
reads the `CAPABILITIES` tuple of that module. Discovery is composition, never a
filesystem scan. The router names no capability.

The command line is always three tokens: `<project> <capability> <function>`.
The group token is the capability directory name with underscores turned to
hyphens, and each public function of that capability's `api.py` is one
subcommand under the same rule. The router derives options, help, envelopes,
paging and exit codes from stdlib-typed signatures and stdlib exceptions, so a
capability writes no command-line code and never selects an exit code.

Two rules govern every docstring the router renders. `argparse` turns a whole
module docstring into the group's help description. It rewraps that text into
one paragraph, so a table or a fenced code block loses every line break.
`argparse` also turns the first line of a function's docstring into the
one-line summary of a command list. Write that first line so it stands alone.

`CLI001` to `CLI004` of the gate reject an api surface that the router cannot
render, so a project fails at commit time rather than at run time. The refusals
here are the second line of that defense, and each one gives one envelope rather
than a traceback.

The forever rule: every future router feature is additive and optional, and the
pack never requires an edit to `composition.py` or to `cli.py`.
"""

import argparse
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
import importlib
import inspect
from itertools import islice
from pathlib import Path
import sys
import traceback
from types import ModuleType, NoneType, UnionType
from typing import NoReturn, TextIO, cast, get_args, get_origin, override

from .cli_outcomes import (
    COMPOSITION_INVALID,
    DEPENDENCY_UNAVAILABLE,
    INVALID_CONTINUATION,
    INVALID_SYNTAX,
    PERMANENT_REJECTION,
    UNEXPECTED_FAILURE,
    ExitCode,
    OutcomeSpec,
)
from .cli_protocol import (
    FailureBody,
    InvalidContinuationError,
    decode_continuation,
    encode_continuation,
    write_failure,
    write_success,
)

__all__ = ["Command", "CompositionError", "main"]

# The router reads its own package name from its own module name, so this file
# holds no project identity and a pack update replaces it whole.
PACKAGE = __name__.split(".", maxsplit=1)[0]
COMPOSITION_MODULE = f"{PACKAGE}.composition"
CAPABILITIES_ATTRIBUTE = "CAPABILITIES"

# The four names that the router turns into an option of every command. `CLI001`
# refuses a capability parameter that claims one of them.
RESERVED_PARAMETERS = frozenset({"continuation", "debug", "format", "limit"})

# A capability parameter reaches argparse under this prefix, so no parameter
# name can collide with a name that the router owns.
VALUE_PREFIX = "value_"
GROUP_DEST = "capability"
FUNCTION_DEST = "function"
COMMAND_DEST = "command"

# The scalar annotations that the router renders as one command-line value. Each
# one builds its value from one string, so it is its own argparse converter.
SCALAR_TYPES: tuple[object, ...] = (str, int, float, Path)

# The machine envelope is the one shipped format. The option exists so that a
# later format is additive and the command line never changes.
FORMAT_CHOICES = ("json",)
DEFAULT_LIMIT = 50


class CompositionError(RuntimeError):
    """Raised when the composition root cannot give the router a command set."""


class ParseRejectionError(Exception):
    """Raised in place of the argparse exit, so that the router writes the envelope."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Command:
    """One subcommand: one public function of one composed capability."""

    group: str
    name: str
    function: Callable[..., object]
    signature: inspect.Signature
    group_documentation: str
    documentation: str
    query: bool

    @property
    def label(self) -> str:
        """The two tokens that name this command inside an envelope."""
        return f"{self.group} {self.name}"


# --- The composition root -----------------------------------------------------


def load_capabilities() -> tuple[object, ...]:
    """Read `CAPABILITIES` from the composition root of this project."""
    try:
        module = importlib.import_module(COMPOSITION_MODULE)
    except ImportError as error:
        message = f"The composition root {COMPOSITION_MODULE} does not import: {error}"
        raise CompositionError(message) from error
    entries = cast("object", getattr(module, CAPABILITIES_ATTRIBUTE, None))
    if not isinstance(entries, tuple):
        message = f"The composition root {COMPOSITION_MODULE} states no {CAPABILITIES_ATTRIBUTE}."
        raise CompositionError(message)
    return cast("tuple[object, ...]", entries)


def unique_entries(entries: Sequence[object]) -> tuple[object, ...]:
    """The composed entries in order, deduplicated by identity."""
    seen: list[int] = []
    unique: list[object] = []
    for entry in entries:
        if id(entry) in seen:
            continue
        seen.append(id(entry))
        unique.append(entry)
    return tuple(unique)


def entry_origin(entry: object) -> str:
    """The module that one composed entry comes from."""
    return entry.__name__ if isinstance(entry, ModuleType) else type(entry).__module__


def capability_name(entry: object) -> str:
    """The capability directory of one entry: the first segment after the package."""
    module = entry_origin(entry)
    parts = module.split(".")
    if parts[0] != PACKAGE or len(parts) < 2 or parts[1].startswith("_"):
        raise CompositionError(f"Composed entry '{module}' is not a capability of this project.")
    return parts[1]


def public_callables(entry: object) -> tuple[tuple[str, Callable[..., object]], ...]:
    """Every public function of an api module, or public method of a bound object."""
    if isinstance(entry, ModuleType):
        return tuple(
            (name, member)
            for name, member in inspect.getmembers(entry, inspect.isfunction)
            if not name.startswith("_") and member.__module__ == entry.__name__
        )
    return tuple(
        (name, member)
        for name, member in inspect.getmembers(entry, inspect.ismethod)
        if not name.startswith("_")
    )


def build_commands(entries: Sequence[object]) -> tuple[Command, ...]:
    """One command per public function of each composed capability.

    One capability gives one command group, so two entries that give one group
    name are a defect of the composition root rather than a merge.
    """
    commands: list[Command] = []
    owners: dict[str, str] = {}
    for entry in unique_entries(entries):
        group = capability_name(entry).replace("_", "-")
        origin = entry_origin(entry)
        if group in owners:
            message = f"Entries '{owners[group]}' and '{origin}' both give the group '{group}'."
            raise CompositionError(message)
        owners[group] = origin
        documentation = inspect.getdoc(entry) or ""
        for name, function in public_callables(entry):
            commands.append(_command(group, documentation, name, function))
    return tuple(commands)


def discover_commands() -> tuple[Command, ...]:
    """The whole command set of this project, read from the composition root."""
    return build_commands(load_capabilities())


# --- One signature becomes one command ----------------------------------------


def _is_query(annotation: object) -> bool:
    """An `Iterator[...]` return is a query, and every other return is one document."""
    return annotation is Iterator or get_origin(annotation) is Iterator


def _annotation(parameter: inspect.Parameter) -> object:
    """The annotation of one parameter, read as an opaque object."""
    return cast("object", parameter.annotation)


def _default(parameter: inspect.Parameter) -> object:
    """The default of one parameter, read as an opaque object."""
    return cast("object", parameter.default)


def _scalar(annotation: object) -> object:
    """The one scalar type of a parameter annotation, with a `None` arm removed."""
    if isinstance(annotation, UnionType):
        arms = [
            arm for arm in cast("tuple[object, ...]", get_args(annotation)) if arm is not NoneType
        ]
        return arms[0] if len(arms) == 1 else None
    return annotation


def _reject_unrenderable(where: str, parameter: inspect.Parameter) -> None:
    """Refuse a parameter that the router cannot turn into one command-line value."""
    name = parameter.name
    if name in RESERVED_PARAMETERS:
        raise CompositionError(f"Parameter '{name}' of '{where}' is a reserved router option.")
    if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
        raise CompositionError(f"Parameter '{name}' of '{where}' is variadic.")
    scalar = _scalar(_annotation(parameter))
    if scalar is not bool and scalar not in SCALAR_TYPES:
        raise CompositionError(f"Parameter '{name}' of '{where}' states an unrenderable type.")


def _command(group: str, documentation: str, name: str, function: Callable[..., object]) -> Command:
    """One command, after every parameter of the function is renderable."""
    signature = inspect.signature(function)
    where = f"{group} {name}"
    for parameter in signature.parameters.values():
        _reject_unrenderable(where, parameter)
    return Command(
        group=group,
        name=name.replace("_", "-"),
        function=function,
        signature=signature,
        group_documentation=documentation,
        documentation=inspect.getdoc(function) or "",
        query=_is_query(cast("object", signature.return_annotation)),
    )


def _flag(name: str) -> str:
    """The long option of one parameter name."""
    return "--" + name.replace("_", "-")


def _add_positional(
    parser: argparse.ArgumentParser, parameter: inspect.Parameter, converter: object
) -> None:
    """Add one positional-only parameter, which stays a command-line positional."""
    destination = VALUE_PREFIX + parameter.name
    build = cast("Callable[[str], object]", converter)
    default = _default(parameter)
    if default is inspect.Parameter.empty:
        _ = parser.add_argument(destination, metavar=parameter.name, type=build)
        return
    _ = parser.add_argument(
        destination,
        metavar=parameter.name,
        type=build,
        nargs="?",
        default=default,
    )


def _add_parameter(parser: argparse.ArgumentParser, parameter: inspect.Parameter) -> None:
    """Add one capability parameter: a positional, a value option, or a presence flag."""
    destination = VALUE_PREFIX + parameter.name
    scalar = _scalar(_annotation(parameter))
    if scalar is bool:
        _ = parser.add_argument(_flag(parameter.name), dest=destination, action="store_true")
        return
    if parameter.kind is inspect.Parameter.POSITIONAL_ONLY:
        _add_positional(parser, parameter, scalar)
        return
    default = _default(parameter)
    required = default is inspect.Parameter.empty
    _ = parser.add_argument(
        _flag(parameter.name),
        dest=destination,
        metavar=parameter.name.upper(),
        type=cast("Callable[[str], object]", scalar),
        required=required,
        default=None if required else default,
    )


def _page_size(text: str) -> int:
    """An argparse converter for a page size, which is one or more."""
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("--limit takes one or more.")
    return value


def _add_router_options(parser: argparse.ArgumentParser, *, query: bool) -> None:
    """Add the options that the router owns on every command, and paging on a query."""
    _ = parser.add_argument(
        "--format",
        choices=FORMAT_CHOICES,
        default=FORMAT_CHOICES[0],
        help="the output format",
    )
    _ = parser.add_argument("--debug", action="store_true", help="write a traceback on a failure")
    if not query:
        return
    _ = parser.add_argument("--limit", type=_page_size, default=DEFAULT_LIMIT, help="the page size")
    _ = parser.add_argument("--continuation", default="", help="the token of the previous page")


class Parser(argparse.ArgumentParser):
    """An argument parser that rejects an invocation rather than ending the process."""

    @override
    def error(self, message: str) -> NoReturn:
        raise ParseRejectionError(message)


def _summary(documentation: str) -> str:
    """The first line of a docstring, which argparse shows in a command list."""
    return documentation.splitlines()[0] if documentation else ""


def _configure(parser: argparse.ArgumentParser, command: Command) -> None:
    """Give one subcommand parser its parameters, its options and its command."""
    for parameter in command.signature.parameters.values():
        _add_parameter(parser, parameter)
    _add_router_options(parser, query=command.query)
    parser.set_defaults(**{COMMAND_DEST: command})


def _grouped(commands: Sequence[Command]) -> tuple[tuple[str, tuple[Command, ...]], ...]:
    """Every command, gathered under its capability group, in composition order."""
    groups: dict[str, list[Command]] = {}
    for command in commands:
        groups.setdefault(command.group, []).append(command)
    return tuple((group, tuple(items)) for group, items in groups.items())


def build_parser(commands: Sequence[Command]) -> Parser:
    """One parser: one command group per capability, one subcommand per function."""
    parser = Parser(description="Run one function of one composed capability.")
    groups = parser.add_subparsers(dest=GROUP_DEST, metavar="capability", required=True)
    for group, owned in _grouped(commands):
        documentation = owned[0].group_documentation
        functions = groups.add_parser(
            group, help=_summary(documentation), description=documentation
        ).add_subparsers(dest=FUNCTION_DEST, metavar="function", required=True)
        for command in owned:
            _configure(
                functions.add_parser(
                    command.name,
                    help=_summary(command.documentation),
                    description=command.documentation,
                ),
                command,
            )
    return parser


# --- Running one command ------------------------------------------------------


def _read(values: argparse.Namespace, destination: str) -> object:
    """One parsed value, read as an opaque object rather than as an unknown type."""
    return cast("object", getattr(values, destination))


def _arguments(
    command: Command, values: argparse.Namespace
) -> tuple[list[object], dict[str, object]]:
    """The positional and the keyword arguments of one call."""
    positional: list[object] = []
    keyword: dict[str, object] = {}
    for name, parameter in command.signature.parameters.items():
        value = _read(values, VALUE_PREFIX + name)
        if parameter.kind is inspect.Parameter.POSITIONAL_ONLY:
            positional.append(value)
        else:
            keyword[name] = value
    return positional, keyword


def _selection(command: Command, values: argparse.Namespace) -> dict[str, object]:
    """The query selection that a continuation token is bound to."""
    selection: dict[str, object] = {COMMAND_DEST: command.label}
    for name in command.signature.parameters:
        value = _read(values, VALUE_PREFIX + name)
        selection[name] = str(value) if isinstance(value, Path) else value
    return selection


def _start(token: str, selection: dict[str, object]) -> int:
    """The position that the token names, or zero when no token is given."""
    if not token:
        return 0
    position = decode_continuation(token, selection=selection)
    if not position.isdigit():
        raise InvalidContinuationError(
            "The continuation token has an invalid position.", reason="invalid_position"
        )
    return int(position)


def _run_query(command: Command, values: argparse.Namespace, out: TextIO) -> None:
    """Run one query and write one page, with the token of the next page."""
    positional, keyword = _arguments(command, values)
    selection = _selection(command, values)
    start = _start(cast("str", _read(values, "continuation")), selection)
    limit = cast("int", _read(values, "limit"))
    items = cast("Iterator[object]", command.function(*positional, **keyword))
    page = list(islice(items, start, start + limit))
    remaining = next(items, None) is not None
    token = encode_continuation(str(start + limit), selection=selection) if remaining else ""
    write_success(
        command=command.label,
        data=page,
        metadata={"count": len(page), "continuation": token},
        out=out,
    )


def _run_document(command: Command, values: argparse.Namespace, out: TextIO) -> None:
    """Run one command and write one document."""
    positional, keyword = _arguments(command, values)
    write_success(
        command=command.label,
        data=command.function(*positional, **keyword),
        metadata={},
        out=out,
    )


def _fail(
    label: str, outcome: OutcomeSpec, error: BaseException, err: TextIO, *, debug: bool
) -> int:
    """Write one envelope for one raised exception, and return its exit code."""
    if debug:
        traceback.print_exception(error, file=err)
    write_failure(command=label, failure=FailureBody(outcome=outcome, message=str(error)), err=err)
    return int(outcome.exit_code)


def run(command: Command, values: argparse.Namespace, out: TextIO, err: TextIO) -> int:
    """Run one command, and map every raised exception to one envelope and exit code."""
    debug = bool(_read(values, "debug"))
    label = command.label
    try:
        if command.query:
            _run_query(command, values, out)
        else:
            _run_document(command, values, out)
    except InvalidContinuationError as error:
        return _fail(label, INVALID_CONTINUATION, error, err, debug=debug)
    except (ValueError, LookupError) as error:
        return _fail(label, PERMANENT_REJECTION, error, err, debug=debug)
    except (ConnectionError, TimeoutError, OSError) as error:
        return _fail(label, DEPENDENCY_UNAVAILABLE, error, err, debug=debug)
    except Exception as error:
        return _fail(label, UNEXPECTED_FAILURE, error, err, debug=debug)
    return int(ExitCode.SUCCESS)


def main(
    argv: Sequence[str] | None = None,
    *,
    out: TextIO | None = None,
    err: TextIO | None = None,
) -> int:
    """Run one command line and return its exit code. This function is the one entry point."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    stream_out = sys.stdout if out is None else out
    stream_err = sys.stderr if err is None else err
    try:
        commands = discover_commands()
    except CompositionError as error:
        return _fail("", COMPOSITION_INVALID, error, stream_err, debug=False)
    parser = build_parser(commands)
    try:
        values = parser.parse_args(arguments)
    except ParseRejectionError as error:
        return _fail("", INVALID_SYNTAX, error, stream_err, debug=False)
    except SystemExit as request:
        return request.code if isinstance(request.code, int) else int(ExitCode.SUCCESS)
    return run(cast("Command", _read(values, COMMAND_DEST)), values, stream_out, stream_err)
