import os
from contextlib import asynccontextmanager

import joblib
import pandas as pd
import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

DB_HOST = os.environ["DB_HOST"]
DB_PORT = os.environ["DB_PORT"]
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_NAME = os.environ["DB_NAME"]

MODEL_PATH = "/app/artifacts/model.joblib"
TTF_MODEL_PATH = "/app/artifacts/ttf_model.joblib"
FEATURE_COLS_PATH = "/app/artifacts/feature_cols.joblib"

PUBLISH_INTERVAL = int(os.getenv("PUBLISH_INTERVAL", "5"))
WINDOW_SIZES = [5, 10, 20]
LAG_STEPS = [1, 3, 5, 10]
LOOKBACK = 30

model = None
ttf_model = None
feature_cols = None


def get_db():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, dbname=DB_NAME
    )


def load_model():
    global model, ttf_model, feature_cols
    if not os.path.exists(MODEL_PATH):
        return
    model = joblib.load(MODEL_PATH)
    feature_cols = joblib.load(FEATURE_COLS_PATH)
    if os.path.exists(TTF_MODEL_PATH):
        ttf_model = joblib.load(TTF_MODEL_PATH)


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_model()
    yield


app = FastAPI(title="IoT Prediction API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def fetch_recent(device_id: str) -> pd.DataFrame:
    conn = get_db()
    try:
        query = """
            SELECT time, device_id, metric, value
            FROM sensor_data
            WHERE device_id = %s
            ORDER BY time DESC
            LIMIT %s
        """
        df = pd.read_sql(query, conn, params=(device_id, LOOKBACK * 3))
    finally:
        conn.close()
    return df.sort_values("time").reset_index(drop=True)


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df["time"] = pd.to_datetime(df["time"]).dt.floor("s")
    pivoted = df.pivot_table(
        index=["time", "device_id"],
        columns="metric",
        values="value",
        aggfunc="first",
    ).reset_index()
    pivoted.columns.name = None

    metric_cols = [c for c in ["temperature", "humidity", "pressure"] if c in pivoted.columns]

    for col in metric_cols:
        for lag in LAG_STEPS:
            pivoted[f"{col}_lag{lag}"] = pivoted[col].shift(lag)
        for w in WINDOW_SIZES:
            pivoted[f"{col}_rmean{w}"] = pivoted[col].rolling(w, min_periods=1).mean()
            pivoted[f"{col}_rstd{w}"] = pivoted[col].rolling(w, min_periods=1).std()
        pivoted[f"{col}_diff1"] = pivoted[col].diff()

    pivoted = pivoted.dropna().reset_index(drop=True)
    return pivoted


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": model is not None}


@app.get("/predict/{device_id}")
def predict(device_id: str):
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded. Run training first.")

    raw = fetch_recent(device_id)
    if raw.empty:
        raise HTTPException(status_code=404, detail=f"No data found for {device_id}")

    df = build_features(raw)
    if df.empty:
        raise HTTPException(status_code=400, detail="Not enough data to build features")

    latest = df.iloc[[-1]][feature_cols]
    proba = model.predict_proba(latest)[0]
    prediction = int(model.predict(latest)[0])

    result = {
        "device_id": device_id,
        "failure_predicted": bool(prediction),
        "confidence": round(float(proba[prediction]), 4),
        "failure_probability": round(float(proba[1]), 4),
        "estimated_time_to_failure": None,
    }

    if prediction == 1 and ttf_model is not None:
        ticks = max(0, float(ttf_model.predict(latest)[0]))
        seconds = ticks * PUBLISH_INTERVAL
        mins, secs = divmod(int(seconds), 60)
        hrs, mins = divmod(mins, 60)
        parts = []
        if hrs:
            parts.append(f"{hrs}h")
        if mins:
            parts.append(f"{mins}m")
        parts.append(f"{secs}s")
        result["estimated_time_to_failure"] = " ".join(parts)
        result["estimated_ticks"] = round(ticks, 1)
        result["estimated_seconds"] = round(seconds, 1)

    return result


@app.get("/predict")
def predict_all():
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded. Run training first.")

    results = []
    for device_id in ["device-001", "device-002", "device-003"]:
        try:
            results.append(predict(device_id))
        except HTTPException:
            results.append({"device_id": device_id, "error": "insufficient data"})
    return results


@app.get("/sensors/recent")
def recent_data(device_id: str = None, limit: int = 50):
    conn = get_db()
    try:
        if device_id:
            query = """
                SELECT time, device_id, metric, value, failure
                FROM sensor_data WHERE device_id = %s
                ORDER BY time DESC LIMIT %s
            """
            df = pd.read_sql(query, conn, params=(device_id, limit))
        else:
            query = """
                SELECT time, device_id, metric, value, failure
                FROM sensor_data ORDER BY time DESC LIMIT %s
            """
            df = pd.read_sql(query, conn, params=(limit,))
    finally:
        conn.close()

    return df.to_dict(orient="records")


@app.get("/alerts/recent")
def recent_alerts(limit: int = 50):
    conn = get_db()
    try:
        query = """
            SELECT time, device_id, probability, channel, status
            FROM alerts ORDER BY time DESC LIMIT %s
        """
        df = pd.read_sql(query, conn, params=(limit,))
    finally:
        conn.close()
    return df.to_dict(orient="records")
