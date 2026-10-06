import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import AwareDatetime, BaseModel

from . import db
from .auth import require_token
from .burn import burn_provider
from .config import settings
from .estimator import EstimateRefused, FoodItem, Totals, estimate_meal, reduce_image


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="calorie-balance", lifespan=lifespan, dependencies=[Depends(require_token)])

Db = Annotated[sqlite3.Connection, Depends(db.get_db)]


class Meal(Totals):
    id: int
    eaten_at: datetime
    description: str
    confidence: str
    notes: str
    items: list[FoodItem]
    has_photo: bool
    model: str | None


class MealUpdate(BaseModel):
    eaten_at: AwareDatetime
    description: str
    notes: str = ""
    items: list[FoodItem]


class Balance(BaseModel):
    date: date
    eaten_kcal: float
    eaten_protein_g: float
    eaten_carbs_g: float
    eaten_fat_g: float
    burned_kcal: int
    burned_source: str
    balance_kcal: float  # eaten − burned: positive = surplus, negative = deficit


def _to_meal(row: sqlite3.Row, items: list[sqlite3.Row]) -> Meal:
    return Meal(
        id=row["id"],
        eaten_at=db.from_db_ts(row["eaten_at"]),
        description=row["description"],
        confidence=row["confidence"],
        notes=row["notes"],
        items=[FoodItem(**{k: i[k] for k in FoodItem.model_fields}) for i in items],
        has_photo=row["photo"] is not None,
        model=row["model"],
    )


def _today() -> date:
    return datetime.now(ZoneInfo(settings.timezone)).date()


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    """Start and end of a calendar day in the configured timezone."""
    tz = ZoneInfo(settings.timezone)
    start = datetime.combine(day, time.min, tz)
    return start, datetime.combine(day + timedelta(days=1), time.min, tz)


def _meals_on(conn: sqlite3.Connection, day: date) -> list[Meal]:
    return [_to_meal(r, i) for r, i in db.list_meals(conn, *_day_bounds(day))]


@app.post("/meals", status_code=201)
async def create_meal_from_photo(
    conn: Db, photo: UploadFile, eaten_at: Annotated[AwareDatetime | None, Form()] = None
) -> Meal:
    """Estimate a meal from a photo and save it. The app then edits (PUT) or discards (DELETE) it."""
    if not (photo.content_type or "").startswith("image/"):
        raise HTTPException(415, "Upload an image")
    jpeg = reduce_image(await photo.read())
    try:
        estimate = await estimate_meal(jpeg)
    except EstimateRefused as e:
        raise HTTPException(422, str(e))

    photo_name = f"{uuid.uuid4().hex}.jpg"
    (settings.photos_dir / photo_name).write_bytes(jpeg)
    meal_id = db.insert_meal(
        conn,
        eaten_at=eaten_at or datetime.now(UTC),
        description=estimate.description,
        confidence=estimate.confidence,
        notes=estimate.notes,
        items=estimate.items,
        photo=photo_name,
        model=settings.food_model,
    )
    return _to_meal(*db.get_meal(conn, meal_id))


@app.get("/meals")
def list_meals(conn: Db, date: date | None = None) -> list[Meal]:
    """Meals eaten on a day (default: today), oldest first."""
    return _meals_on(conn, date or _today())


@app.get("/meals/{meal_id}")
def get_meal(conn: Db, meal_id: int) -> Meal:
    found = db.get_meal(conn, meal_id)
    if found is None:
        raise HTTPException(404, "Meal not found")
    return _to_meal(*found)


@app.put("/meals/{meal_id}")
def update_meal(conn: Db, meal_id: int, update: MealUpdate) -> Meal:
    updated = db.update_meal(
        conn,
        meal_id,
        eaten_at=update.eaten_at,
        description=update.description,
        notes=update.notes,
        items=update.items,
    )
    if not updated:
        raise HTTPException(404, "Meal not found")
    return _to_meal(*db.get_meal(conn, meal_id))


@app.delete("/meals/{meal_id}", status_code=204)
def delete_meal(conn: Db, meal_id: int) -> None:
    row = db.delete_meal(conn, meal_id)
    if row is None:
        raise HTTPException(404, "Meal not found")
    if row["photo"]:
        (settings.photos_dir / row["photo"]).unlink(missing_ok=True)


@app.get("/meals/{meal_id}/photo", response_class=FileResponse)
def get_meal_photo(conn: Db, meal_id: int):
    found = db.get_meal(conn, meal_id)
    if found is None or found[0]["photo"] is None:
        raise HTTPException(404, "Photo not found")
    return FileResponse(settings.photos_dir / found[0]["photo"], media_type="image/jpeg")


@app.get("/balance")
async def get_balance(conn: Db, date: date | None = None) -> Balance:
    """Eaten vs. burned for a day (default: today)."""
    day = date or _today()
    meals = _meals_on(conn, day)
    burn = await burn_provider.get_daily_burn(day)
    eaten = sum(m.total_kcal for m in meals)
    return Balance(
        date=day,
        eaten_kcal=eaten,
        eaten_protein_g=round(sum(m.total_protein_g for m in meals), 1),
        eaten_carbs_g=round(sum(m.total_carbs_g for m in meals), 1),
        eaten_fat_g=round(sum(m.total_fat_g for m in meals), 1),
        burned_kcal=burn.total_kcal,
        burned_source=burn.source,
        balance_kcal=eaten - burn.total_kcal,
    )
