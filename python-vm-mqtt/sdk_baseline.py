"""
Laboratorio 3 - Etapa 1 / baseline: mismo dispositivo Python del Laboratorio 2
(python-vm-01), publicando con el SDK oficial azure-iot-device.

Sirve de punto de comparacion frente a mqtt_explicito.py: aqui el SDK
esconde el provisionamiento DPS, la firma de tokens SAS y los topics MQTT
reales; en mqtt_explicito.py se hace todo eso a mano.

Variables de entorno esperadas (ver README.md):
  ID_SCOPE, DEVICE_ID, PRIMARY_KEY
Opcionales para las mediciones de la Etapa 3:
  INTERVAL_SEC (default 10), COUNT (default 0 = infinito), LOG_CSV
"""
import asyncio
import csv
import json
import os
import random
import time
from pathlib import Path

from azure.iot.device.aio import IoTHubDeviceClient, ProvisioningDeviceClient
from azure.iot.device import Message
from dotenv import load_dotenv

load_dotenv()

ID_SCOPE = os.environ["ID_SCOPE"]
DEVICE_ID = os.environ["DEVICE_ID"]
PRIMARY_KEY = os.environ["PRIMARY_KEY"]
INTERVAL_SEC = float(os.environ.get("INTERVAL_SEC", "10"))
COUNT = int(os.environ.get("COUNT", "0"))
LOG_CSV = os.environ.get("LOG_CSV", "mediciones_sdk.csv")
PROVISIONING_HOST = "global.azure-devices-provisioning.net"


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


async def provision():
    prov_client = ProvisioningDeviceClient.create_from_symmetric_key(
        provisioning_host=PROVISIONING_HOST,
        registration_id=DEVICE_ID,
        id_scope=ID_SCOPE,
        symmetric_key=PRIMARY_KEY,
    )
    result = await prov_client.register()
    if result.status != "assigned":
        raise RuntimeError(f"Provisioning DPS fallo: status={result.status}")
    return result.registration_state.assigned_hub


async def main():
    print(f"[DPS-SDK] Provisionando {DEVICE_ID} (SDK azure-iot-device) ...")
    assigned_hub = await provision()
    print(f"[DPS-SDK] Asignado a hub: {assigned_hub}")

    client = IoTHubDeviceClient.create_from_symmetric_key(
        symmetric_key=PRIMARY_KEY,
        hostname=assigned_hub,
        device_id=DEVICE_ID,
    )
    await client.connect()
    print("[SDK] Conectado.")

    sent = 0
    try:
        while COUNT == 0 or sent < COUNT:
            payload_dict = make_payload()
            payload = json.dumps(payload_dict)
            msg = Message(payload)
            msg.content_encoding = "utf-8"
            msg.content_type = "application/json"

            t0 = time.time()
            await client.send_message(msg)
            t1 = time.time()

            row = {
                "timestamp_publish": t0,
                "payload_bytes": len(payload.encode("utf-8")),
                "interval_configurado_s": INTERVAL_SEC,
                "latencia_send_sdk_s": round(t1 - t0, 4),
                "humidity": payload_dict["humidity"],
                "illuminance": payload_dict["illuminance"],
                "temperature": payload_dict["temperature"],
            }
            log_row(row)
            print(f"[SDK PUBLISH] {payload} ({len(payload.encode('utf-8'))} bytes)")

            sent += 1
            await asyncio.sleep(INTERVAL_SEC)
    except KeyboardInterrupt:
        pass
    finally:
        await client.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
