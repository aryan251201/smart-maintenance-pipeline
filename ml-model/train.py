"""Training pipeline — pull data from TimescaleDB, engineer features, train model."""

import os
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import classification_report, mean_absolute_error
from sklearn.model_selection import train_test_split
from sqlalchemy import create_engine

DB_HOST = os.environ["DB_HOST"]
DB_PORT = os.environ["DB_PORT"]
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_NAME = os.environ["DB_NAME"]

ARTIFACT_DIR = "/app/artifacts"
MODEL_PATH = os.path.join(ARTIFACT_DIR, "model.joblib")
TTF_MODEL_PATH = os.path.join(ARTIFACT_DIR, "ttf_model.joblib")
FEATURE_COLS_PATH = os.path.join(ARTIFACT_DIR, "feature_cols.joblib")

INTERVAL = int(os.getenv("PUBLISH_INTERVAL", "5"))
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
    raw = raw.copy()
    raw["time"] = raw["time"].dt.floor("s")

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
    """Label rows within `lookahead` ticks before a failure as positive.
    Also computes ticks_to_failure for regression (NaN for normal rows)."""
    df["label"] = 0
    df["ticks_to_failure"] = np.nan
    for device in df["device_id"].unique():
        mask = df["device_id"] == device
        device_df = df.loc[mask]
        failure_idxs = device_df.index[device_df["failure"] == True]
        for idx in failure_idxs:
            start = max(idx - lookahead, device_df.index[0])
            df.loc[start:idx, "label"] = 1
            for i in range(start, idx + 1):
                df.loc[i, "ticks_to_failure"] = idx - i
    return df


def train():
    df = build_features(pivot_metrics(df_raw_global))
    df = label_prefailure(df)

    feature_cols = [
        c for c in df.columns
        if c not in ["time", "device_id", "failure", "label", "ticks_to_failure"]
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

    model = HistGradientBoostingClassifier(
        max_iter=200,
        max_depth=4,
        learning_rate=0.1,
        min_samples_leaf=10,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    print("\n--- Classification Performance ---")
    print(classification_report(y_test, y_pred, zero_division=0))

    # --- Time-to-failure regression model (trained only on pre-failure rows) ---
    prefail = df[df["label"] == 1].copy()
    X_ttf = prefail[feature_cols]
    y_ttf = prefail["ticks_to_failure"]

    X_ttf_train, X_ttf_test, y_ttf_train, y_ttf_test = train_test_split(
        X_ttf, y_ttf, test_size=0.2, shuffle=False
    )

    ttf_model = HistGradientBoostingRegressor(
        max_iter=200,
        max_depth=4,
        learning_rate=0.1,
        min_samples_leaf=10,
    )
    ttf_model.fit(X_ttf_train, y_ttf_train)

    y_ttf_pred = ttf_model.predict(X_ttf_test)
    mae = mean_absolute_error(y_ttf_test, y_ttf_pred)
    print(f"\n--- Time-to-Failure Regression ---")
    print(f"MAE: {mae:.2f} ticks ({mae * INTERVAL:.0f} seconds)")

    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    joblib.dump(ttf_model, TTF_MODEL_PATH)
    joblib.dump(feature_cols, FEATURE_COLS_PATH)
    print(f"\nClassifier saved to {MODEL_PATH}")
    print(f"TTF regressor saved to {TTF_MODEL_PATH}")
    print(f"Feature columns saved to {FEATURE_COLS_PATH}")

    from sklearn.inspection import permutation_importance
    perm = permutation_importance(model, X_test, y_test, n_repeats=5, random_state=42)
    importances = sorted(
        zip(feature_cols, perm.importances_mean), key=lambda x: -x[1]
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
