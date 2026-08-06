"""A deliberately false contract that CrossHair must refute."""

import icontract


def _denies_echo(value: str, result: str) -> bool:
    return result != value


@icontract.ensure(
    _denies_echo,
    description="SYMBOLIC-CANARY: CrossHair must refute this deliberately false postcondition",
)
def refutable_echo(value: str) -> str:
    """Echo one symbolic value so the false postcondition has a counterexample."""
    return value
