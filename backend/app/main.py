from fastapi import FastAPI, HTTPException, UploadFile

from .estimator import EstimateRefused, MealEstimate, estimate_meal

app = FastAPI(title="calorie-balance")


@app.post("/meals/estimate")
async def estimate(photo: UploadFile) -> MealEstimate:
    if not (photo.content_type or "").startswith("image/"):
        raise HTTPException(415, "Upload an image")
    try:
        return await estimate_meal(await photo.read())
    except EstimateRefused as e:
        raise HTTPException(422, str(e))
