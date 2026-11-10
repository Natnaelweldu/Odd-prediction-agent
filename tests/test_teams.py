import pytest
from fqae.core import db, teams


@pytest.fixture
def conn():
    return db.connect(":memory:")


def test_unknown_name_fails_loudly(conn):
    with pytest.raises(teams.UnknownTeam):
        teams.resolve(conn, "fd", "Man City")


def test_alias_resolves_to_same_canonical_id(conn):
    teams.register(conn, "fd", "Man City", name="Manchester City", team_id="man_city")
    teams.register(conn, "api_football", "Manchester City", team_id="man_city")
    assert teams.resolve(conn, "fd", "Man City") == "man_city"
    assert teams.resolve(conn, "api_football", "Manchester City") == "man_city"


def test_alias_is_per_source(conn):
    teams.register(conn, "fd", "Man City", team_id="man_city")
    with pytest.raises(teams.UnknownTeam):
        teams.resolve(conn, "api_football", "Man City")


def test_slugify_and_bootstrap(conn):
    assert teams.resolve(conn, "fd", "Nott'm Forest", bootstrap=True) == "nott_m_forest"
    assert teams.unmapped(conn, "fd", ["Nott'm Forest", "Luton"]) == ["Luton"]
