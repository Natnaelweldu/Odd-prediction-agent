import pytest

from fqae.adapters import api_football, fd_csv
from fqae.core import db, quality, teams
from tests.test_fd_loader import FIX


def test_quality_clean_fixture_has_no_issues():
    conn = db.connect(":memory:")
    fd_csv.ingest(conn, fd_csv.read_csv(FIX / "2324_E0.csv"), "E0", "2324", bootstrap=True)
    assert quality.run_checks(conn) == []


def test_quality_flags_bad_rows():
    conn = db.connect(":memory:")
    df = fd_csv.read_csv(FIX / "2324_E0.csv")
    df.loc[0, "FTR"] = "H"          # score says away win
    df.loc[1, "PSCH"] = 1.01        # absurd overround
    fd_csv.ingest(conn, df, "E0", "2324", bootstrap=True)
    msgs = " | ".join(quality.run_checks(conn))
    assert "FTR disagrees" in msgs and "overround" in msgs


def test_api_football_parse_resolves_names():
    conn = db.connect(":memory:")
    teams.register(conn, "api_football", "Manchester City", team_id="man_city")
    teams.register(conn, "api_football", "Arsenal", team_id="arsenal")
    resp = [{"fixture": {"id": 99, "date": "2026-11-14T15:00:00+00:00", "status": {"short": "NS"}},
             "teams": {"home": {"name": "Arsenal"}, "away": {"name": "Manchester City"}}}]
    out = api_football.parse_fixtures(conn, resp)
    assert out[0]["fixture_id"] == "api-football:99" and out[0]["away_id"] == "man_city"
    resp[0]["teams"]["away"]["name"] = "Man. City"
    with pytest.raises(teams.UnknownTeam):
        api_football.parse_fixtures(conn, resp)
