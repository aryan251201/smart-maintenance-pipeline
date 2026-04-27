"""IoT device simulator — publishes fake sensor readings to MQTT.

Occasionally simulates failure degradation: a device's metrics gradually
drift toward dangerous levels over a window of ticks, then a failure
event fires, and the device recovers.
"""

import json
import os
import random
import time

import paho.mqtt.client as mqtt

BROKER = os.getenv("MQTT_BROKER", "localhost")
PORT = int(os.getenv("MQTT_PORT", "1883"))
TOPIC = "iot/sensors"
INTERVAL = int(os.getenv("PUBLISH_INTERVAL", "5"))

DEVICES = ["device-001", "device-002", "device-003"]
METRICS = ["temperature", "humidity", "pressure"]

NORMAL_RANGES = {
    "temperature": (15, 35),
    "humidity": (30, 70),
    "pressure": (980, 1030),
}

FAILURE_PEAKS = {
    "temperature": 48.0,
    "humidity": 95.0,
    "pressure": 940.0,
}

DEGRADATION_TICKS = 20
FAILURE_COOLDOWN = int(os.getenv("FAILURE_COOLDOWN", str(120 // 5)))

device_states: dict[str, dict] = {}


def get_state(device_id: str) -> dict:
    if device_id not in device_states:
        device_states[device_id] = {
            "degrading": False,
            "tick": 0,
            "metric": None,
            "cooldown": random.randint(0, FAILURE_COOLDOWN),
        }
    return device_states[device_id]


def maybe_start_degradation(state: dict) -> None:
    if state["degrading"]:
        return
    state["cooldown"] -= 1
    if state["cooldown"] <= 0:
        state["degrading"] = True
        state["tick"] = 0
        state["metric"] = random.choice(METRICS)


def generate_reading(device_id: str, metric: str) -> dict:
    state = get_state(device_id)
    lo, hi = NORMAL_RANGES[metric]
    failure = False

    if state["degrading"] and metric == state["metric"]:
        progress = state["tick"] / DEGRADATION_TICKS
        peak = FAILURE_PEAKS[metric]
        normal_mid = (lo + hi) / 2
        value = normal_mid + (peak - normal_mid) * progress
        value += random.gauss(0, 1)
        if state["tick"] >= DEGRADATION_TICKS:
            failure = True
    else:
        value = random.uniform(lo, hi)

    return {
        "device_id": device_id,
        "metric": metric,
        "value": round(value, 2),
        "failure": failure,
    }


def main():
    client = mqtt.Client()
    client.connect(BROKER, PORT)
    client.loop_start()

    print(f"Simulator connected to {BROKER}:{PORT}")
    while True:
        for device in DEVICES:
            state = get_state(device)
            maybe_start_degradation(state)

            for metric in METRICS:
                payload = generate_reading(device, metric)
                client.publish(TOPIC, json.dumps(payload))

            if state["degrading"]:
                state["tick"] += 1
                if state["tick"] > DEGRADATION_TICKS:
                    print(f"[FAILURE] {device} — {state['metric']} failure event")
                    state["degrading"] = False
                    state["tick"] = 0
                    state["metric"] = None
                    state["cooldown"] = FAILURE_COOLDOWN

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
