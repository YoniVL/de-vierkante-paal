"""Lokale opslag (SQLite). Houdt de laatst opgehaalde data, statistiek-momentopnames
voor de verschil-kolom, handmatige scores en bewaarde afleveringen bij.
"""

from __future__ import annotations

import datetime as _dt
import json
import re as _re
import sqlite3
from typing import Any

from . import config

AFLEVERINGEN_DIR = config.DATA_ROOT / "afleveringen"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stat_snapshot (
    taken_at   TEXT NOT NULL,
    player_key TEXT NOT NULL,
    speler     TEXT NOT NULL,
    apps       INTEGER,
    goals      INTEGER,
    assists    INTEGER,
    yellow     INTEGER,
    red        INTEGER,
    minutes    INTEGER,
    team       TEXT
);
CREATE INDEX IF NOT EXISTS idx_snapshot_player ON stat_snapshot(player_key, taken_at);
CREATE TABLE IF NOT EXISTS manual_rating (
    event_id   TEXT NOT NULL,
    player_key TEXT NOT NULL,
    source     TEXT NOT NULL,
    rating     REAL,
    PRIMARY KEY (event_id, player_key, source)
);
CREATE TABLE IF NOT EXISTS episode (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    title      TEXT NOT NULL,
    payload    TEXT NOT NULL,
    team       TEXT
);
"""


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


def init() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        # migraties voor bestaande databases
        snap_kol = {r["name"] for r in conn.execute("PRAGMA table_info(stat_snapshot)")}
        for kolom in ("yellow", "red"):
            if kolom not in snap_kol:
                conn.execute(f"ALTER TABLE stat_snapshot ADD COLUMN {kolom} INTEGER")
        if "team" not in snap_kol:
            conn.execute("ALTER TABLE stat_snapshot ADD COLUMN team TEXT")
        ep_kol = {r["name"] for r in conn.execute("PRAGMA table_info(episode)")}
        if "team" not in ep_kol:
            conn.execute("ALTER TABLE episode ADD COLUMN team TEXT")


def backfill_team(standaard_team: str) -> None:
    """Bestaande rijen zonder ploeg toewijzen aan de huidige standaardploeg
    (databases van vóór de meerdere-ploegen-versie)."""
    with _connect() as conn:
        conn.execute("UPDATE stat_snapshot SET team=? WHERE team IS NULL", (standaard_team,))
        conn.execute("UPDATE episode SET team=? WHERE team IS NULL", (standaard_team,))


# --- key/value --------------------------------------------------------------
def set_kv(key: str, value: Any) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO kv(key, value, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, json.dumps(value, ensure_ascii=False), _now()),
        )


def get_kv(key: str, default: Any = None) -> Any:
    with _connect() as conn:
        row = conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def get_kv_updated(key: str) -> str | None:
    with _connect() as conn:
        row = conn.execute("SELECT updated_at FROM kv WHERE key=?", (key,)).fetchone()
    return row["updated_at"] if row else None


def del_kv(*keys: str) -> None:
    if not keys:
        return
    with _connect() as conn:
        conn.executemany("DELETE FROM kv WHERE key=?", [(k,) for k in keys])


# --- statistiek-momentopnames ----------------------------------------------
def save_stat_snapshot(spelers: list[dict], team: str | None = None) -> None:
    """``spelers`` = lijst met keys: player_key, speler, apps, goals, assists, yellow, red, minutes."""
    ts = _now()
    with _connect() as conn:
        conn.executemany(
            "INSERT INTO stat_snapshot(taken_at, player_key, speler, apps, goals, assists, yellow, red, minutes, team) "
            "VALUES(:taken_at, :player_key, :speler, :apps, :goals, :assists, :yellow, :red, :minutes, :team)",
            [{"taken_at": ts, "team": team, **s} for s in spelers],
        )


def previous_stat_snapshot(team: str | None = None) -> dict[str, dict]:
    """De op één na recentste momentopname per speler (voor de verschil-kolom),
    voor de opgegeven ploeg."""
    with _connect() as conn:
        rounds = [
            r["taken_at"]
            for r in conn.execute(
                "SELECT DISTINCT taken_at FROM stat_snapshot WHERE team IS ? ORDER BY taken_at DESC",
                (team,),
            ).fetchall()
        ]
        if len(rounds) < 2:
            return {}
        target = rounds[1]
        rows = conn.execute(
            "SELECT player_key, apps, goals, assists, yellow, red, minutes "
            "FROM stat_snapshot WHERE taken_at=? AND team IS ?",
            (target, team),
        ).fetchall()
    return {r["player_key"]: dict(r) for r in rows}


# --- handmatige scores -----------------------------------------------------
def save_manual_rating(event_id: str, player_key: str, source: str, rating: float | None) -> None:
    with _connect() as conn:
        if rating is None:
            conn.execute(
                "DELETE FROM manual_rating WHERE event_id=? AND player_key=? AND source=?",
                (event_id, player_key, source),
            )
        else:
            conn.execute(
                "INSERT INTO manual_rating(event_id, player_key, source, rating) VALUES(?,?,?,?) "
                "ON CONFLICT(event_id, player_key, source) DO UPDATE SET rating=excluded.rating",
                (event_id, player_key, source, rating),
            )


def manual_ratings(event_id: str) -> dict[tuple[str, str], float]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT player_key, source, rating FROM manual_rating WHERE event_id=?",
            (event_id,),
        ).fetchall()
    return {(r["player_key"], r["source"]): r["rating"] for r in rows}


# --- afleveringen ---------------------------------------------------------
def _slug(tekst: str) -> str:
    return _re.sub(r"[^a-z0-9]+", "-", tekst.lower()).strip("-")[:60] or "aflevering"


def save_episode(title: str, payload: dict, markdown: str = "", notities: str = "",
                 team: str | None = None, team_map: str = "") -> dict:
    """Bewaart in SQLite én als los Markdown-bestand in de map ``afleveringen/``
    (met een submap per ploeg in de generieke variant)."""
    ts = _now()
    bestand = ""
    volledig = markdown
    if notities.strip():
        volledig = f"{markdown}\n\n## Eigen notities\n\n{notities.strip()}\n"
    if volledig:
        map_ = AFLEVERINGEN_DIR / team_map if team_map else AFLEVERINGEN_DIR
        map_.mkdir(parents=True, exist_ok=True)
        pad = map_ / f"{ts[:10]}_{_slug(title)}.md"
        pad.write_text(volledig, encoding="utf-8")
        bestand = str(pad)
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO episode(created_at, title, payload, team) VALUES(?,?,?,?)",
            (ts, title, json.dumps(
                {"overzicht": payload, "markdown": volledig, "notities": notities.strip(),
                 "bestand": bestand}, ensure_ascii=False), team),
        )
    return {"id": int(cur.lastrowid), "bestand": bestand}


def list_episodes(team: str | None = None) -> list[dict]:
    with _connect() as conn:
        if team is None:
            rows = conn.execute(
                "SELECT id, created_at, title, payload FROM episode ORDER BY id DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, created_at, title, payload FROM episode WHERE team IS ? ORDER BY id DESC",
                (team,),
            ).fetchall()
    uit = []
    for r in rows:
        try:
            bestand = json.loads(r["payload"]).get("bestand", "")
        except Exception:
            bestand = ""
        uit.append({"id": r["id"], "created_at": r["created_at"], "title": r["title"], "bestand": bestand})
    return uit


def get_episode(episode_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM episode WHERE id=?", (episode_id,)).fetchone()
    if not row:
        return None
    data = json.loads(row["payload"])
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "title": row["title"],
        "markdown": data.get("markdown", ""),
        "notities": data.get("notities", ""),
        "bestand": data.get("bestand", ""),
        "overzicht": data.get("overzicht", data),
    }
