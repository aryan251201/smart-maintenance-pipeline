const nodemailer = require("nodemailer");
const { Pool } = require("pg");

const MODEL_API_URL = process.env.MODEL_API_URL || "http://model-api:8000";
const POLL_INTERVAL = parseInt(process.env.POLL_INTERVAL || "10000", 10);
const PROBABILITY_THRESHOLD = parseFloat(process.env.PROBABILITY_THRESHOLD || "0.7");
const COOLDOWN_MS = parseInt(process.env.ALERT_COOLDOWN || "300000", 10);

const pool = new Pool({
  host: process.env.DB_HOST,
  port: parseInt(process.env.DB_PORT, 10),
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
});

const lastAlerted = {};

function shouldAlert(deviceId) {
  const last = lastAlerted[deviceId] || 0;
  return Date.now() - last > COOLDOWN_MS;
}

let twilioClient = null;
const TWILIO_FROM = process.env.TWILIO_FROM_NUMBER;
const ALERT_TO = process.env.ALERT_TO_NUMBER;
if (process.env.TWILIO_ACCOUNT_SID && process.env.TWILIO_AUTH_TOKEN) {
  const twilio = require("twilio");
  twilioClient = twilio(
    process.env.TWILIO_ACCOUNT_SID,
    process.env.TWILIO_AUTH_TOKEN
  );
  console.log("Twilio SMS alerts enabled");
}

let emailTransporter = null;
const ALERT_EMAIL = process.env.ALERT_EMAIL;
if (process.env.SMTP_HOST && process.env.SMTP_USER) {
  emailTransporter = nodemailer.createTransport({
    host: process.env.SMTP_HOST,
    port: parseInt(process.env.SMTP_PORT || "587", 10),
    secure: false,
    auth: {
      user: process.env.SMTP_USER,
      pass: process.env.SMTP_PASS,
    },
  });
  console.log("Email alerts enabled");
}

async function sendSMS(deviceId, probability, eta) {
  if (!twilioClient || !TWILIO_FROM || !ALERT_TO) return "skipped";
  try {
    const etaText = eta ? ` — ETA: ${eta}` : "";
    await twilioClient.messages.create({
      body: `[IoT ALERT] ${deviceId} failure predicted — probability: ${(probability * 100).toFixed(1)}%${etaText}`,
      from: TWILIO_FROM,
      to: ALERT_TO,
    });
    return "sent";
  } catch (err) {
    console.error("SMS error:", err.message);
    return "failed";
  }
}

async function sendEmail(deviceId, probability, eta) {
  if (!emailTransporter || !ALERT_EMAIL) return "skipped";
  try {
    await emailTransporter.sendMail({
      from: process.env.SMTP_USER,
      to: ALERT_EMAIL,
      subject: `[IoT ALERT] ${deviceId} — failure in ${eta || "unknown"}`,
      text: [
        `Device: ${deviceId}`,
        `Failure probability: ${(probability * 100).toFixed(1)}%`,
        `Estimated time to failure: ${eta || "unknown"}`,
        `Time: ${new Date().toISOString()}`,
        "",
        "Check the dashboard for details.",
      ].join("\n"),
    });
    return "sent";
  } catch (err) {
    console.error("Email error:", err.message);
    return "failed";
  }
}

async function logAlert(deviceId, probability, channel, status) {
  try {
    await pool.query(
      "INSERT INTO alerts (device_id, probability, channel, status) VALUES ($1, $2, $3, $4)",
      [deviceId, probability, channel, status]
    );
  } catch (err) {
    console.error("DB log error:", err.message);
  }
}

async function pollAndAlert() {
  try {
    const res = await fetch(`${MODEL_API_URL}/predict`);
    if (!res.ok) {
      console.error("Model API error:", res.status);
      return;
    }

    const predictions = await res.json();

    for (const pred of predictions) {
      if (pred.error) continue;
      if (pred.failure_probability < PROBABILITY_THRESHOLD) continue;
      if (!shouldAlert(pred.device_id)) continue;

      const eta = pred.estimated_time_to_failure || "unknown";
      console.log(
        `[ALERT] ${pred.device_id} — failure probability: ${(pred.failure_probability * 100).toFixed(1)}% — ETA: ${eta}`
      );

      lastAlerted[pred.device_id] = Date.now();

      const smsStatus = await sendSMS(pred.device_id, pred.failure_probability, eta);
      const emailStatus = await sendEmail(pred.device_id, pred.failure_probability, eta);

      await logAlert(pred.device_id, pred.failure_probability, "sms", smsStatus);
      await logAlert(pred.device_id, pred.failure_probability, "email", emailStatus);
    }
  } catch (err) {
    console.error("Poll error:", err.message);
  }
}

console.log(
  `Alert service started — polling every ${POLL_INTERVAL / 1000}s, threshold: ${PROBABILITY_THRESHOLD}`
);
setInterval(pollAndAlert, POLL_INTERVAL);
pollAndAlert();
