"""Properties and boundary regressions for the one ownership predicate."""

from string import ascii_lowercase, digits

from hypothesis import given, strategies as st
import pytest

from scripts.ownership import pack_owned
from scripts.ownership_specifications import pack_owned_is_exact
from verification.harness.assertions import assert_falsifies, assert_property

# A stand-in package name that rule R2 of the projection can never admit, so
# this pack-owned file cannot collide with its own project's identity.
PACKAGE = "PLACEHOLDER_PACKAGE"
SEGMENTS = st.text(alphabet=ascii_lowercase + digits + "_-.", min_size=1, max_size=24)
USER_NAMES = st.text(alphabet=ascii_lowercase + digits + "-", min_size=1, max_size=24)
PACK_OWNED_NAMES = st.one_of(USER_NAMES.map(lambda name: f"_{name}"), st.just("py.typed"))
LEAVES = st.lists(SEGMENTS, min_size=0, max_size=3)
CANDIDATES = st.one_of(
    LEAVES.map(lambda leaf: "/".join(("pack", *leaf))),
    st.tuples(PACK_OWNED_NAMES, LEAVES).map(
        lambda item: "/".join(("src", PACKAGE, item[0], *item[1]))
    ),
    st.tuples(USER_NAMES, LEAVES).map(lambda item: "/".join(("src", PACKAGE, item[0], *item[1]))),
    st.tuples(USER_NAMES, LEAVES).map(lambda item: "/".join((item[0], *item[1]))),
    st.lists(SEGMENTS, min_size=1, max_size=4).map("/".join),
)


@pytest.mark.proof
@pytest.mark.proves("PACK::PACK-OWNED")
@given(candidate=CANDIDATES)
def test_the_predicate_answers_exactly_the_pack_owned_surface(candidate: str) -> None:
    result = pack_owned(candidate, PACKAGE)

    assert_property(
        condition=pack_owned_is_exact(candidate, PACKAGE, result=result),
        property_id="PACK::PACK-OWNED",
    )


@pytest.mark.proof
@pytest.mark.falsifies("PACK::PACK-OWNED")
def test_a_pack_prefixed_sibling_is_a_real_counterexample() -> None:
    assert_falsifies(
        condition=pack_owned_is_exact("packages/report.py", PACKAGE, result=True),
        property_id="PACK::PACK-OWNED",
    )


def test_every_path_under_the_pack_directory_is_pack_owned() -> None:
    assert pack_owned("pack", PACKAGE) is True
    assert pack_owned("pack/configs/ruff.toml", PACKAGE) is True
    assert pack_owned("pack/scripts/ownership.py", PACKAGE) is True


def test_underscore_names_and_the_typed_marker_are_pack_owned() -> None:
    assert pack_owned(f"src/{PACKAGE}/py.typed", PACKAGE) is True
    assert pack_owned(f"src/{PACKAGE}/__init__.py", PACKAGE) is True
    assert pack_owned(f"src/{PACKAGE}/_foundation/router.py", PACKAGE) is True


def test_every_other_name_in_the_package_is_user_owned() -> None:
    assert pack_owned(f"src/{PACKAGE}/cli.py", PACKAGE) is False
    assert pack_owned(f"src/{PACKAGE}/composition.py", PACKAGE) is False
    assert pack_owned(f"src/{PACKAGE}/billing/api.py", PACKAGE) is False


def test_the_package_directory_itself_is_user_owned() -> None:
    assert pack_owned(f"src/{PACKAGE}", PACKAGE) is False
    assert pack_owned("src", PACKAGE) is False


def test_another_package_under_the_source_root_is_user_owned() -> None:
    assert pack_owned("src/OTHER_PACKAGE/_foundation/router.py", PACKAGE) is False


def test_a_user_owned_entry_point_is_not_pack_owned() -> None:
    assert pack_owned("justfile", PACKAGE) is False
    assert pack_owned("pyrightconfig.json", PACKAGE) is False
    assert pack_owned(".github/workflows/quality.yml", PACKAGE) is False
