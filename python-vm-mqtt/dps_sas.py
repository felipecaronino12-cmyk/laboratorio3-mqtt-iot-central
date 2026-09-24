"""
Provisionamiento DPS + generacion manual de tokens SAS, sin el SDK azure-iot-device.
Usado por mqtt_explicito.py para conectarse a IoT Central "a mano" por MQTT puro.
"""
import base64
import hashlib
import hmac
import time
import urllib.parse

import requests

DPS_GLOBAL_ENDPOINT = "global.azure-devices-provisioning.net"
API_VERSION = "2021-06-01"


def _sign(resource_uri: str, key: str, expiry_epoch: int, key_name: str | None = None) -> str:
    """Genera un token SAS estilo IoT Hub/DPS: SharedAccessSignature sr=...&sig=...&se=...[&skn=...]"""
    encoded_uri = urllib.parse.quote_plus(resource_uri)
    string_to_sign = f"{encoded_uri}\n{expiry_epoch}"
    key_bytes = base64.b64decode(key)
    signature = base64.b64encode(
        hmac.new(key_bytes, string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    )
    encoded_sig = urllib.parse.quote_plus(signature)
    token = f"SharedAccessSignature sr={encoded_uri}&sig={encoded_sig}&se={expiry_epoch}"
    if key_name:
        token += f"&skn={key_name}"
    return token


def provision_device(id_scope: str, device_id: str, primary_key: str, ttl_seconds: int = 3600) -> dict:
    """
    Registra el dispositivo contra DPS usando autenticacion por clave simetrica
    y devuelve {"assigned_hub": ..., "device_id": ...}.
    """
    expiry = int(time.time()) + ttl_seconds
    resource_uri = f"{id_scope}/registrations/{device_id}"
    sas = _sign(resource_uri, primary_key, expiry, key_name="registration")

    headers = {"Content-Type": "application/json", "Authorization": sas}
    register_url = (
        f"https://{DPS_GLOBAL_ENDPOINT}/{id_scope}/registrations/{device_id}/register"
        f"?api-version={API_VERSION}"
    )
    resp = requests.put(register_url, json={"registrationId": device_id}, headers=headers, timeout=15)
    resp.raise_for_status()
    operation_id = resp.json()["operationId"]

    status_url = (
        f"https://{DPS_GLOBAL_ENDPOINT}/{id_scope}/registrations/{device_id}/operations/{operation_id}"
        f"?api-version={API_VERSION}"
    )
    for _ in range(10):
        time.sleep(2)
        poll = requests.get(status_url, headers=headers, timeout=15)
        poll.raise_for_status()
        body = poll.json()
        if body.get("status") == "assigned":
            state = body["registrationState"]
            return {"assigned_hub": state["assignedHub"], "device_id": state["deviceId"]}
        if body.get("status") == "failed":
            raise RuntimeError(f"Provisioning DPS fallo: {body}")
    raise TimeoutError("DPS no asigno el dispositivo a tiempo (timeout de polling)")


def hub_sas_token(hub_hostname: str, device_id: str, primary_key: str, ttl_seconds: int = 3600) -> str:
    """Token SAS para autenticar el MQTT CONNECT contra el IoT Hub asignado."""
    expiry = int(time.time()) + ttl_seconds
    resource_uri = f"{hub_hostname}/devices/{device_id}"
    return _sign(resource_uri, primary_key, expiry)
