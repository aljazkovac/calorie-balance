import io
import os
import tempfile

import pytest
from PIL import Image

TEST_TOKEN = "test-token-" + "x" * 32

# Settings are read at import time, so configure them before importing the app.
# Environment variables take precedence over the real .env file.
os.environ.update(
    ANTHROPIC_API_KEY="test-key",
    APP_TOKEN=TEST_TOKEN,
    DATA_DIR=tempfile.mkdtemp(prefix="calorie-balance-test-"),
    TIMEZONE="Europe/Stockholm",
    FIXED_BURNED_KCAL="2500",
)

from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402
from app.estimator import FoodItem, ModelEstimate  # noqa: E402

FAKE_ESTIMATE = ModelEstimate(
    description="Test omelette",
    items=[
        FoodItem(name="Eggs", grams=150, kcal=215, protein_g=18.8, carbs_g=1.1, fat_g=14.3),
        FoodItem(name="Butter", grams=7, kcal=55, protein_g=0, carbs_g=0, fat_g=6),
    ],
    confidence="medium",
    notes="synthetic",
)


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(main.settings, "data_dir", tmp_path)

    async def fake_estimate(jpeg: bytes) -> ModelEstimate:
        assert jpeg.startswith(b"\xff\xd8")  # it's a JPEG
        return FAKE_ESTIMATE

    monkeypatch.setattr(main, "estimate_meal", fake_estimate)
    with TestClient(main.app, headers={"Authorization": f"Bearer {TEST_TOKEN}"}) as c:
        yield c


@pytest.fixture
def photo() -> bytes:
    """A synthetic 'photo': a plain 3000×2000 image."""
    buf = io.BytesIO()
    Image.new("RGB", (3000, 2000), (200, 150, 100)).save(buf, format="JPEG")
    return buf.getvalue()
