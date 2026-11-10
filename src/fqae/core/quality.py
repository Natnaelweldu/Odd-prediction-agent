"""Data-quality checks on the matches table (task 0.10)."""
import sqlite3


def run_checks(conn: sqlite3.Connection) -> list[str]:
    issues = []
    q = lambda sql: conn.execute(sql).fetchall()
    for r in q("SELECT match_id FROM matches WHERE fthg IS NULL OR ftag IS NULL"):
        issues.append(f"missing score: {r[0]}")
    for r in q("SELECT match_id FROM matches WHERE ftr != CASE WHEN fthg>ftag THEN 'H' WHEN fthg<ftag THEN 'A' ELSE 'D' END"):
        issues.append(f"FTR disagrees with score: {r[0]}")
    for r in q("""SELECT match_id, 1/psch+1/pscd+1/psca AS o FROM matches
                  WHERE psch IS NOT NULL AND pscd IS NOT NULL AND psca IS NOT NULL
                  AND (1/psch+1/pscd+1/psca < 1.0 OR 1/psch+1/pscd+1/psca > 1.15)"""):
        issues.append(f"Pinnacle closing overround {r[1]:.3f} outside [1.00,1.15]: {r[0]}")
    for r in q("""SELECT div, season, COUNT(*) n, SUM(psch IS NULL) miss FROM matches
                  GROUP BY div, season HAVING miss*1.0/n > 0.10"""):
        issues.append(f"{r[0]} {r[1]}: {r[3]}/{r[2]} matches missing Pinnacle closing odds")
    for r in q("""SELECT match_date, home_id, away_id, COUNT(*) FROM matches
                  GROUP BY match_date, home_id, away_id HAVING COUNT(*)>1"""):
        issues.append(f"duplicate match {r[0]} {r[1]} v {r[2]}")
    for r in q("SELECT match_id FROM matches WHERE home_id=away_id"):
        issues.append(f"team plays itself: {r[0]}")
    return issues
