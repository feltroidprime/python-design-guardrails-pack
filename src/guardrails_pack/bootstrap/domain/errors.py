"""The one error of the capability, and the shape of every refusal message.

A refusal is a permanent rejection of the request, so it is a `ValueError`. The
router maps `ValueError` to the permanent-rejection envelope and to exit code 3
(#85 section 3.1), which is why this capability never selects an exit code.

Every refusal message has the same four parts, in this order: the rule that
fired, what is wrong, why the rule exists, and what to do instead. It ends with
one promise, and the promise is always the same sentence.
"""

__all__ = ["NOTHING_WAS_WRITTEN", "RefusalError", "refuse"]

# The last sentence of every refusal of `R1` to `R9`. The projection makes each
# check it can before it writes, builds in a temporary directory, checks the
# result, then moves the tree into place as one operation. So the promise holds
# for every refusal, and a reader needs to know only this one sentence.
NOTHING_WAS_WRITTEN = "Nothing was written."


class RefusalError(ValueError):
    """Raised when a projection refuses a request. The disk stays untouched."""


def refuse(rule: str, wrong: str, why: str, instead: str) -> RefusalError:
    """Build one refusal of one rule, in the four fixed parts plus the promise."""
    return RefusalError(f"{rule}: {wrong} {why} {instead} {NOTHING_WAS_WRITTEN}")
