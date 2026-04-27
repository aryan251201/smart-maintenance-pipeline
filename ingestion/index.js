const mqtt = require("mqtt");
const { Pool } = require("pg");

const mqttClient = mqtt.connect(
  `mqtt://${process.env.MQTT_BROKER}:${process.env.MQTT_PORT}`
);

const pool = new Pool({
  host: process.env.DB_HOST,
  port: parseInt(process.env.DB_PORT, 10),
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
});

mqttClient.on("connect", () => {
  console.log("Ingestion service connected to MQTT");
  mqttClient.subscribe("iot/sensors");
});

mqttClient.on("message", async (_topic, message) => {
  try {
    const { device_id, metric, value, failure } = JSON.parse(message.toString());
    await pool.query(
      "INSERT INTO sensor_data (time, device_id, metric, value, failure) VALUES (NOW(), $1, $2, $3, $4)",
      [device_id, metric, value, failure ?? false]
    );
  } catch (err) {
    console.error("Ingestion error:", err.message);
  }
});
