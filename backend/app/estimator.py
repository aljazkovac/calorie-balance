import base64
import io
from typing import Literal

from anthropic import AsyncAnthropic
from PIL import Image, ImageOps
from pydantic import BaseModel, Field, computed_field

from .config import settings

# Larger images only cost more tokens; Claude downscales beyond roughly this anyway.
MAX_IMAGE_EDGE = 1568

PROMPT = """\
Estimate the nutritional content of the meal in this photo.

List every distinct food item you can see, including likely hidden calories
(cooking oil, butter, dressings, sauces). For each item estimate the portion in
grams, then its calories and macronutrients for that portion.

Use the plate, cutlery and packaging as scale references. If something is
ambiguous, pick the most likely interpretation and mention it in `notes`.
"""


class FoodItem(BaseModel):
    name: str
    grams: float
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


class ModelEstimate(BaseModel):
    """What we ask Claude for. Totals are computed in code, not by the model."""

    description: str = Field(description="Short name for the whole meal")
    items: list[FoodItem]
    confidence: Literal["low", "medium", "high"]
    notes: str


class Totals(BaseModel):
    """Adds totals computed from `items` to any model that has them."""

    items: list[FoodItem]

    @computed_field
    @property
    def total_kcal(self) -> float:
        return round(sum(i.kcal for i in self.items))

    @computed_field
    @property
    def total_protein_g(self) -> float:
        return round(sum(i.protein_g for i in self.items), 1)

    @computed_field
    @property
    def total_carbs_g(self) -> float:
        return round(sum(i.carbs_g for i in self.items), 1)

    @computed_field
    @property
    def total_fat_g(self) -> float:
        return round(sum(i.fat_g for i in self.items), 1)


class EstimateRefused(Exception):
    pass


client = AsyncAnthropic(api_key=settings.anthropic_api_key)


def reduce_image(data: bytes) -> bytes:
    """Fix phone EXIF rotation, downscale and re-encode as JPEG."""
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    img.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=85)
    return buf.getvalue()


async def estimate_meal(jpeg: bytes) -> ModelEstimate:
    """Ask Claude for an estimate of a JPEG produced by `reduce_image`."""
    response = await client.beta.messages.parse(
        model=settings.food_model,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": base64.standard_b64encode(jpeg).decode(),
                        },
                    },
                    {"type": "text", "text": PROMPT},
                ],
            }
        ],
        output_format=ModelEstimate,
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise EstimateRefused(f"No estimate (stop_reason={response.stop_reason})")
    return response.parsed_output
