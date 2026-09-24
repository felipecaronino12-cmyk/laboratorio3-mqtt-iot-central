# Wokwi — Laboratorio 3

El firmware del ESP32 **no cambió** respecto al Laboratorio 2: ya
implementaba MQTT/TLS puro (sin SDK), con DPS por HTTPS + SAS firmado a
mano con `mbedtls`, exactamente el mismo patrón que `mqtt_explicito.py`
pero en C++. Por eso no se duplica el código aquí — se reutiliza el mismo
proyecto:

**Proyecto Wokwi:** https://wokwi.com/projects/474815106090292225
**Dispositivo IoT Central:** `esp32-wokwi-02` (mismo de Lab 2)

## Verificación para el Laboratorio 3 (2026-09-24)

Se volvió a correr la simulación y se confirmó en el portal:

- Estado: **Conectado**.
- Ciclo `Desconectado -> Conectado` visible en **Datos sin procesar**
  (15:48:38 Desconectado, 15:48:43 Conectado), cumpliendo el requisito de
  mostrar una transición real de conexión.
- Telemetría real llegando cada ~10 s con los 3 valores del modelo
  (`humidity`, `illuminance`, `temperature`), formato JSON idéntico al de
  los otros dos caminos (SDK y MQTT explícito).

Ver capturas en [`../evidencias/`](../evidencias/).

## Por qué no hay una versión "SDK" de este nodo

No existe un SDK oficial de Azure IoT activamente mantenido para
Arduino/ESP32 (el que existía, `azure-sdk-for-c-arduino`, está archivado).
Por eso el ESP32 siempre fue, desde el Laboratorio 2, el ejemplo real de
"MQTT explícito" en hardware embebido — no hay otra opción en esta
plataforma, lo cual es en sí mismo parte de la conclusión de la Etapa 4 de
este laboratorio (ver [`../comparativa.md`](../comparativa.md)).
