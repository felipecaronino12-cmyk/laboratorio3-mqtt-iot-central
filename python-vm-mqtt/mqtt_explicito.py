"""
Laboratorio 3 - Etapa 2: cliente MQTT explicito contra Azure IoT Central,
sin pasar por el SDK azure-iot-device.

Hace a mano lo que el SDK esconde:
  1. Provisionamiento DPS (HTTPS + SAS) -> obtiene el IoT Hub asignado.
  2. Token SAS para el CONNECT de MQTT.
  3. Conexion MQTT/TLS directa con paho-mqtt (puerto 8883).
  4. Publish de telemetria al topic de eventos del dispositivo.
  5. Subscribe a twin (respuesta) y a C2D, para poder ver un comando/property.

Variables de entorno esperadas (ver README.md, nunca hardcodear secretos):
  ID_SCOPE, DEVICE_ID, PRIMARY_KEY
Opcionales para las mediciones de la Etapa 3:
  INTERVAL_SEC (default 10), QOS (default 1), COUNT (default 0 = infinito),
  LOG_CSV (default mediciones.csv)
"""
import csv
import json
import os
import random
import ssl
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from dps_sas import hub_sas_token, provision_device

load_dotenv()

ID_SCOPE = os.environ["ID_SCOPE"]
DEVICE_ID = os.environ["DEVICE_ID"]
PRIMARY_KEY = os.environ["PRIMARY_KEY"]
INTERVAL_SEC = float(os.environ.get("INTERVAL_SEC", "10"))
QOS = int(os.environ.get("QOS", "1"))
COUNT = int(os.environ.get("COUNT", "0"))
LOG_CSV = os.environ.get("LOG_CSV", "mediciones.csv")

connected_evt = {"connected": False, "last_disconnect": None}


def log_row(row: dict):
    exists = Path(LOG_CSV).exists()
    with open(LOG_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def make_payload():
    return {
        "humidity": round(random.uniform(35, 70), 1),
        "illuminance": round(random.uniform(100, 900), 1),
        "temperature": round(random.uniform(16, 32), 1),
    }


def on_connect(client, userdata, flags, reason_code, properties=None):
    print(f"[MQTT] CONNACK reason_code={reason_code}")
    connected_evt["connected"] = reason_code == 0 or str(reason_code) == "Success"
    client.subscribe("$iothub/twin/res/#", qos=1)
    client.subscribe("devices/{}/messages/devicebound/#".format(DEVICE_ID), qos=1)
    print("[MQTT] Suscrito a twin/res y a C2D (devicebound)")


def on_disconnect(client, userdata, reason_code, properties=None):
    connected_evt["connected"] = False
    connected_evt["last_disconnect"] = time.time()
    print(f"[MQTT] Desconectado. reason_code={reason_code}")


def on_message(client, userdata, msg):
    print(f"[MQTT] <- topic={msg.topic} payload={msg.payload[:200]!r}")


def on_publish(client, userdata, mid, reason_code=None, properties=None):
    print(f"[MQTT] PUBACK/complete mid={mid}")


def build_client(hub_hostname: str) -> mqtt.Client:
    client = mqtt.Client(client_id=DEVICE_ID, protocol=mqtt.MQTTv311)
    username = f"{hub_hostname}/{DEVICE_ID}/?api-version=2021-04-12"
    password = hub_sas_token(hub_hostname, DEVICE_ID, PRIMARY_KEY)
    client.username_pw_set(username=username, password=password)
    client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.on_publish = on_publish
    return client


def main():
    print(f"[DPS] Provisionando {DEVICE_ID} en id_scope={ID_SCOPE} ...")
    result = provision_device(ID_SCOPE, DEVICE_ID, PRIMARY_KEY)
    hub_hostname = result["assigned_hub"]
    print(f"[DPS] Asignado a hub: {hub_hostname}")

    client = build_client(hub_hostname)
    client.connect(hub_hostname, port=8883, keepalive=60)
    client.loop_start()

    topic = f"devices/{DEVICE_ID}/messages/events/"
    sent = 0
    try:
        while COUNT == 0 or sent < COUNT:
            if not connected_evt["connected"]:
                time.sleep(1)
                continue
            payload_dict = make_payload()
            payload = json.dumps(payload_dict)
            payload_bytes = payload.encode("utf-8")

            t0 = time.time()
            info = client.publish(topic, payload=payload_bytes, qos=QOS)
            info.wait_for_publish(timeout=10)
            t1 = time.time()

            row = {
                "timestamp_publish": t0,
                "payload_bytes": len(payload_bytes),
                "qos": QOS,
                "interval_configurado_s": INTERVAL_SEC,
                "latencia_publish_local_s": round(t1 - t0, 4),
                "humidity": payload_dict["humidity"],
                "illuminance": payload_dict["illuminance"],
                "temperature": payload_dict["temperature"],
            }
            log_row(row)
            print(f"[PUBLISH] {payload} ({len(payload_bytes)} bytes, qos={QOS}) -> {topic}")

            sent += 1
            time.sleep(INTERVAL_SEC)
    except KeyboardInterrupt:
        print("\n[MAIN] Interrumpido por el usuario.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    sys.exit(main())
