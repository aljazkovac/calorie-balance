import io

from fastapi.testclient import TestClient
from PIL import Image

from app import main


def upload(client, photo: bytes, **form):
    return client.post("/meals", files={"photo": ("meal.jpg", photo, "image/jpeg")}, data=form)


def test_requires_token(client):
    no_auth = TestClient(main.app)
    assert no_auth.get("/meals").status_code == 401
    wrong = TestClient(main.app, headers={"Authorization": "Bearer nope"})
    assert wrong.get("/meals").status_code == 401


def test_create_meal_from_photo(client, photo):
    r = upload(client, photo)
    assert r.status_code == 201
    meal = r.json()
    assert meal["description"] == "Test omelette"
    assert meal["total_kcal"] == 270
    assert meal["total_fat_g"] == 20.3
    assert meal["has_photo"] is True

    # The stored photo is the reduced version.
    r = client.get(f"/meals/{meal['id']}/photo")
    assert r.status_code == 200
    assert max(Image.open(io.BytesIO(r.content)).size) == 1568


def test_rejects_non_image(client):
    r = client.post("/meals", files={"photo": ("notes.txt", b"hello", "text/plain")})
    assert r.status_code == 415


def test_list_meals_by_day(client, photo):
    upload(client, photo, eaten_at="2026-10-05T12:00:00+02:00")
    upload(client, photo, eaten_at="2026-10-05T23:30:00+02:00")
    upload(client, photo, eaten_at="2026-10-06T00:30:00+02:00")  # just after midnight

    assert len(client.get("/meals", params={"date": "2026-10-05"}).json()) == 2
    assert len(client.get("/meals", params={"date": "2026-10-06"}).json()) == 1


def test_update_meal(client, photo):
    meal = upload(client, photo).json()
    update = {
        "eaten_at": "2026-10-05T08:00:00+02:00",
        "description": "Bigger omelette",
        "items": [
            {"name": "Eggs", "grams": 200, "kcal": 290, "protein_g": 25, "carbs_g": 1.5, "fat_g": 19}
        ],
    }
    r = client.put(f"/meals/{meal['id']}", json=update)
    assert r.status_code == 200
    assert r.json()["total_kcal"] == 290
    assert r.json()["eaten_at"] == "2026-10-05T06:00:00Z"
    assert client.get(f"/meals/{meal['id']}").json()["description"] == "Bigger omelette"


def test_delete_meal_removes_photo(client, photo):
    meal = upload(client, photo).json()
    assert len(list(main.settings.photos_dir.iterdir())) == 1

    assert client.delete(f"/meals/{meal['id']}").status_code == 204
    assert client.get(f"/meals/{meal['id']}").status_code == 404
    assert list(main.settings.photos_dir.iterdir()) == []


def test_missing_meal(client):
    assert client.get("/meals/999").status_code == 404
    assert client.delete("/meals/999").status_code == 404


def test_balance(client, photo):
    upload(client, photo, eaten_at="2026-10-05T08:00:00+02:00")
    upload(client, photo, eaten_at="2026-10-05T19:00:00+02:00")

    b = client.get("/balance", params={"date": "2026-10-05"}).json()
    assert b["eaten_kcal"] == 540
    assert b["burned_kcal"] == 2500
    assert b["burned_source"] == "fixed"
    assert b["balance_kcal"] == 540 - 2500
