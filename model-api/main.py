from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="IoT Prediction API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/predict")
def predict():
    # TODO: load model from /app/artifacts, accept features, return prediction
    return {"prediction": None, "message": "not yet implemented"}


@app.get("/sensors/recent")
def recent_data():
    # TODO: query TimescaleDB for last N readings
    return {"data": [], "message": "not yet implemented"}
