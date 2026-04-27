"""Training pipeline — pull data from TimescaleDB, engineer features, train model."""

import os
import sys

import joblib
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sqlalchemy import create_engine

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "iot")
DB_PASSWORD = os.getenv("DB_PASSWORD", "iotpass")
DB_NAME = os.getenv("DB_NAME", "iot_data")

ARTIFACT_DIR = "/app/artifacts"
MODEL_PATH = os.path.join(ARTIFACT_DIR, "model.joblib")
FEATURE_COLS_PATH = os.path.join(ARTIFACT_DIR, "feature_cols.joblib")

WINDOW_SIZES = [5, 10, 20]
LAG_STEPS = [1, 3, 5, 10]


def load_data() -> pd.DataFrame:
    url = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(url)
    df = pd.read_sql(
        "SELECT time, device_id, metric, value, failure FROM sensor_data ORDER BY time",
        engine,
    )
    print(f"Loaded {len(df)} rows from sensor_data")
    return df


def pivot_metrics(raw: pd.DataFrame) -> pd.DataFrame:
    pivoted = raw.pivot_table(
        index=["time", "device_id"],
        columns="metric",
        values="value",
        aggfunc="first",
    ).reset_index()
    pivoted.columns.name = None

    failure_flags = (
        raw.groupby(["time", "device_id"])["failure"]
        .max()
        .reset_index()
    )
    pivoted = pivoted.merge(failure_flags, on=["time", "device_id"])
    return pivoted.sort_values(["device_id", "time"]).reset_index(drop=True)


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    metric_cols = [c for c in ["temperature", "humidity", "pressure"] if c in df.columns]

    for col in metric_cols:
        for lag in LAG_STEPS:
            df[f"{col}_lag{lag}"] = df.groupby("device_id")[col].shift(lag)

        for w in WINDOW_SIZES:
            rolling = df.groupby("device_id")[col].rolling(w, min_periods=1)
            df[f"{col}_rmean{w}"] = rolling.mean().reset_index(level=0, drop=True)
            df[f"{col}_rstd{w}"] = rolling.std().reset_index(level=0, drop=True)

        df[f"{col}_diff1"] = df.groupby("device_id")[col].diff()

    df = df.dropna().reset_index(drop=True)
    return df


def label_prefailure(df: pd.DataFrame, lookahead: int = 10) -> pd.DataFrame:
    """Label rows within `lookahead` ticks before a failure as positive."""
    df["label"] = 0
    for device in df["device_id"].unique():
        mask = df["device_id"] == device
        device_df = df.loc[mask]
        failure_idxs = device_df.index[device_df["failure"] == True]
        for idx in failure_idxs:
            start = max(idx - lookahead, device_df.index[0])
            df.loc[start:idx, "label"] = 1
    return df


def train():
    df = build_features(pivot_metrics(df_raw_global))
    df = label_prefailure(df)

    feature_cols = [
        c for c in df.columns
        if c not in ["time", "device_id", "failure", "label"]
    ]

    X = df[feature_cols]
    y = df["label"]

    pos = y.sum()
    neg = len(y) - pos
    print(f"Samples: {len(y)}  |  positive (pre-failure): {pos}  |  negative: {neg}")

    if pos < 5:
        print("Not enough failure events to train. Let the simulator run longer.")
        sys.exit(1)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, shuffle=False
    )

    model = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.1,
        min_samples_leaf=10,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    print("\n--- Test Set Performance ---")
    print(classification_report(y_test, y_pred, zero_division=0))

    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    joblib.dump(feature_cols, FEATURE_COLS_PATH)
    print(f"Model saved to {MODEL_PATH}")
    print(f"Feature columns saved to {FEATURE_COLS_PATH}")

    importances = sorted(
        zip(feature_cols, model.feature_importances_), key=lambda x: -x[1]
    )
    print("\n--- Top 10 Features ---")
    for name, imp in importances[:10]:
        print(f"  {name:30s} {imp:.4f}")


if __name__ == "__main__":
    df_raw_global = load_data()
    if df_raw_global.empty:
        print("No data in sensor_data. Start the simulator first.")
        sys.exit(1)
    train()
