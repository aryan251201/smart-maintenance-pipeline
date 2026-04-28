CREATE TABLE IF NOT EXISTS sensor_data (
    time        TIMESTAMPTZ NOT NULL,
    device_id   TEXT        NOT NULL,
    metric      TEXT        NOT NULL,
    value       DOUBLE PRECISION NOT NULL,
    failure     BOOLEAN     NOT NULL DEFAULT FALSE
);

SELECT create_hypertable('sensor_data', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_sensor_device ON sensor_data (device_id, time DESC);

CREATE TABLE IF NOT EXISTS alerts (
    id          SERIAL PRIMARY KEY,
    time        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    device_id   TEXT        NOT NULL,
    probability DOUBLE PRECISION NOT NULL,
    channel     TEXT        NOT NULL,
    status      TEXT        NOT NULL
);
