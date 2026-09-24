# Laboratorio 3 — MQTT hacia Azure IoT Central

Protocolo visible, mediciones y comparación SDK vs MQTT explícito vs Wokwi,
sobre la misma app de IoT Central del Laboratorio 1/2.

**App de IoT Central:** UNAB-Ambiental — Monitoreo de Espacios Académicos
(`laboratorio1caro.azureiotcentral.com`)
**Plantilla:** Nodo Ambiental de Aula (ESP32)
**Segmento de cómputo de este laboratorio:** VM nueva y aislada
`laboratorio3caro` (Azure for Students, `rg-laboratorio3caro`, Mexico
Central), creada desde cero específicamente para este laboratorio. No se
reutilizó ninguna VM de otros compañeros ni la máquina compartida del
profesor — solo recursos propios de esta cuenta.

```
laboratorio3/
├── python-vm-mqtt/
│   ├── sdk_baseline.py     Etapa 1: mismo patrón que python-vm-01 (Lab 2), con el SDK azure-iot-device
│   ├── mqtt_explicito.py   Etapa 2: cliente MQTT "a mano" (paho-mqtt), sin el SDK
│   ├── dps_sas.py          Provisionamiento DPS y firma de tokens SAS, usado por mqtt_explicito.py
│   ├── requirements.txt
│   └── .env.example        Plantilla de variables de entorno (sin secretos)
├── mediciones/              CSVs crudos de las pruebas de la Etapa 3
├── informe/
│   └── informe.md
├── comparativa.md
├── evidencias/
└── README.md
```

## 1. Inventario de cómputo

| Recurso | Dónde | Nota |
|---|---|---|
| VM `laboratorio3caro` | Azure for Students, `rg-laboratorio3caro`, Mexico Central | Ubuntu 24.04, `Standard_B2ats_v2`, creada de 0 para este laboratorio |
| Dispositivo `python-vm-01` | IoT Central (mismo de Lab 2) | Etapa 1 — SDK `azure-iot-device`, corre en `laboratorio3caro` |
| Dispositivo `mqtt-explicito-vm` (nuevo) | IoT Central | Etapa 2 — cliente MQTT explícito, corre en `laboratorio3caro` |
| Dispositivo `esp32-wokwi-02` (mismo de Lab 2) | Wokwi | Firmware sin cambios, mismo patrón DPS+MQTT/TLS |

## 2. Cómo generar el SAS y correr cada script (sin secretos en claro)

Los tres valores sensibles (`ID_SCOPE`, `DEVICE_ID`, `PRIMARY_KEY`) se leen
**siempre** de variables de entorno / un archivo `.env` local que **nunca**
se sube al repositorio (ver `.gitignore`). El repo solo trae
`.env.example` como plantilla.

```bash
cd python-vm-mqtt
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Editar .env con los valores reales:
#   ID_SCOPE=<Ámbito de Id de la app, portal IoT Central > dispositivo > Conectar>
#   DEVICE_ID=<Id. de dispositivo>
#   PRIMARY_KEY=<Clave primaria SAS del dispositivo>

# Etapa 1 — baseline con el SDK oficial
python3 sdk_baseline.py

# Etapa 2 — cliente MQTT explícito (DPS a mano + paho-mqtt)
python3 mqtt_explicito.py
```

`dps_sas.py` implementa la firma HMAC-SHA256 + base64 del token SAS
exactamente como lo exige la API REST de DPS y el CONNECT de MQTT contra el
IoT Hub asignado — el mismo cálculo que hace el SDK por debajo, pero
explícito y auditable.

Variables opcionales para las mediciones (`INTERVAL_SEC`, `QOS`, `COUNT`,
`LOG_CSV`) están documentadas en `.env.example`.

## 3. Qué protocolo usa realmente el dispositivo (Etapa 1)

Confirmado con `mqtt_explicito.py` y con el log serial de Wokwi:

- **Transporte:** MQTT 3.1.1 sobre TLS 1.2, puerto **8883**.
- **DPS primero:** el dispositivo se registra vía HTTPS contra
  `global.azure-devices-provisioning.net/{idScope}/registrations/{deviceId}`
  con un token SAS firmado con la clave del dispositivo; DPS responde con el
  IoT Hub asignado (`iotc-631aa800-...-....azure-devices.net` para esta
  app — un solo hub compartido por todos los dispositivos de la app).
- **Luego el hub:** el CONNECT de MQTT usa como *username*
  `{hub}/{deviceId}/?api-version=2021-04-12` y como *password* un segundo
  token SAS (mismo esquema de firma, recurso `{hub}/devices/{deviceId}`).
- **Topic de telemetría:** `devices/{deviceId}/messages/events/`.
- **Intervalo:** 10 s configurado en los 3 nodos (Python SDK, MQTT explícito
  y Wokwi).
- El JSON publicado coincide exactamente con la plantilla real (`humidity`,
  `illuminance`, `temperature`), verificado en **Explorador de datos** /
  **Datos sin procesar** de IoT Central.

## 4. Ver `informe/informe.md` y `comparativa.md`

Ahí están la tabla de mediciones (Etapa 3), la comparación de los 3 caminos
(Etapa 4) y las conclusiones sobre QoS.
