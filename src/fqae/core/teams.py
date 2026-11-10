"""Single team-name mapping table: canonical id + per-source aliases (FR-1.5)."""
import re
import sqlite3
import unicodedata


class UnknownTeam(KeyError):
    """Raised when a source name has no alias. Never guess."""


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
    return s


def register(conn: sqlite3.Connection, source: str, alias: str, name: str | None = None,
             team_id: str | None = None) -> str:
    """Add an alias. Creates the canonical team if team_id is new."""
    tid = team_id or slugify(name or alias)
    conn.execute("INSERT OR IGNORE INTO teams(team_id, name) VALUES (?, ?)", (tid, name or alias))
    conn.execute("INSERT OR REPLACE INTO team_aliases(source, alias, team_id) VALUES (?,?,?)",
                 (source, alias, tid))
    return tid


def resolve(conn: sqlite3.Connection, source: str, alias: str, bootstrap: bool = False) -> str:
    row = conn.execute("SELECT team_id FROM team_aliases WHERE source=? AND alias=?",
                       (source, alias)).fetchone()
    if row:
        return row["team_id"]
    if bootstrap:
        return register(conn, source, alias)
    raise UnknownTeam(f"{source}: unmapped team name {alias!r}")


def unmapped(conn: sqlite3.Connection, source: str, names: list[str]) -> list[str]:
    known = {r["alias"] for r in conn.execute(
        "SELECT alias FROM team_aliases WHERE source=?", (source,))}
    return sorted(set(names) - known)
