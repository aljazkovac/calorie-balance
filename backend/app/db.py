"""SQLite storage for meals. Timestamps are stored as UTC in a fixed ISO format
(`2026-10-06T12:30:00Z`) so they sort and compare correctly as strings."""

import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime

from .config import settings
from .estimator import FoodItem

SCHEMA = """
CREATE TABLE IF NOT EXISTS meals (
    id          INTEGER PRIMARY KEY,
    eaten_at    TEXT NOT NULL,
    description TEXT NOT NULL,
    confidence  TEXT NOT NULL,
    notes       TEXT NOT NULL,
    photo       TEXT,            -- file name in DATA_DIR/photos
    model       TEXT,            -- which Claude model made the estimate
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS meals_eaten_at ON meals (eaten_at);

CREATE TABLE IF NOT EXISTS meal_items (
    id        INTEGER PRIMARY KEY,
    meal_id   INTEGER NOT NULL REFERENCES meals (id) ON DELETE CASCADE,
    position  INTEGER NOT NULL,
    name      TEXT NOT NULL,
    grams     REAL NOT NULL,
    kcal      REAL NOT NULL,
    protein_g REAL NOT NULL,
    carbs_g   REAL NOT NULL,
    fat_g     REAL NOT NULL
);
"""

TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def to_db_ts(dt: datetime) -> str:
    if dt.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return dt.astimezone(UTC).strftime(TS_FORMAT)


def from_db_ts(s: str) -> datetime:
    return datetime.strptime(s, TS_FORMAT).replace(tzinfo=UTC)


def connect() -> sqlite3.Connection:
    # FastAPI may run a request's setup and teardown on different threads.
    conn = sqlite3.connect(settings.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    settings.photos_dir.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)


def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one connection per request."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def insert_meal(
    conn: sqlite3.Connection,
    *,
    eaten_at: datetime,
    description: str,
    confidence: str,
    notes: str,
    items: list[FoodItem],
    photo: str | None,
    model: str | None,
) -> int:
    with conn:
        cur = conn.execute(
            "INSERT INTO meals (eaten_at, description, confidence, notes, photo, model, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                to_db_ts(eaten_at), description, confidence, notes, photo, model,
                to_db_ts(datetime.now(UTC)),
            ),
        )
        _insert_items(conn, cur.lastrowid, items)
    return cur.lastrowid


def update_meal(
    conn: sqlite3.Connection,
    meal_id: int,
    *,
    eaten_at: datetime,
    description: str,
    notes: str,
    items: list[FoodItem],
) -> bool:
    """Replace a meal's editable fields and items. Returns False if it doesn't exist."""
    with conn:
        cur = conn.execute(
            "UPDATE meals SET eaten_at = ?, description = ?, notes = ? WHERE id = ?",
            (to_db_ts(eaten_at), description, notes, meal_id),
        )
        if cur.rowcount == 0:
            return False
        conn.execute("DELETE FROM meal_items WHERE meal_id = ?", (meal_id,))
        _insert_items(conn, meal_id, items)
    return True


def delete_meal(conn: sqlite3.Connection, meal_id: int) -> sqlite3.Row | None:
    """Delete a meal (items cascade). Returns the deleted row, so the caller can remove its photo."""
    with conn:
        row = conn.execute("SELECT * FROM meals WHERE id = ?", (meal_id,)).fetchone()
        if row:
            conn.execute("DELETE FROM meals WHERE id = ?", (meal_id,))
    return row


def get_meal(conn: sqlite3.Connection, meal_id: int) -> tuple[sqlite3.Row, list[sqlite3.Row]] | None:
    row = conn.execute("SELECT * FROM meals WHERE id = ?", (meal_id,)).fetchone()
    if row is None:
        return None
    return row, _items_for(conn, [meal_id])[meal_id]


def list_meals(
    conn: sqlite3.Connection, start: datetime, end: datetime
) -> list[tuple[sqlite3.Row, list[sqlite3.Row]]]:
    """Meals eaten in [start, end), oldest first."""
    rows = conn.execute(
        "SELECT * FROM meals WHERE eaten_at >= ? AND eaten_at < ? ORDER BY eaten_at, id",
        (to_db_ts(start), to_db_ts(end)),
    ).fetchall()
    items = _items_for(conn, [r["id"] for r in rows])
    return [(r, items[r["id"]]) for r in rows]


def _insert_items(conn: sqlite3.Connection, meal_id: int, items: list[FoodItem]) -> None:
    conn.executemany(
        "INSERT INTO meal_items (meal_id, position, name, grams, kcal, protein_g, carbs_g, fat_g)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (meal_id, pos, i.name, i.grams, i.kcal, i.protein_g, i.carbs_g, i.fat_g)
            for pos, i in enumerate(items)
        ],
    )


def _items_for(conn: sqlite3.Connection, meal_ids: list[int]) -> dict[int, list[sqlite3.Row]]:
    result: dict[int, list[sqlite3.Row]] = {mid: [] for mid in meal_ids}
    if not meal_ids:
        return result
    placeholders = ",".join("?" * len(meal_ids))
    for row in conn.execute(
        f"SELECT * FROM meal_items WHERE meal_id IN ({placeholders}) ORDER BY meal_id, position",
        meal_ids,
    ):
        result[row["meal_id"]].append(row)
    return result
