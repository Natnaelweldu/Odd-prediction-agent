from fqae.jobs.live_check import summarise


def test_summarise_detects_pinnacle():
    ev = [{"commence_time": "2026-11-14T15:00:00Z", "bookmakers": [{"key": "pinnacle"}, {"key": "bet365"}]},
          {"commence_time": "2026-11-13T12:00:00Z", "bookmakers": [{"key": "bet365"}]}]
    s = summarise(ev)
    assert s["pinnacle"] and s["events"] == 2 and s["bookmakers"]["bet365"] == 2
    assert s["first_kickoff"] == "2026-11-13T12:00:00Z"
    assert not summarise([])["pinnacle"]
