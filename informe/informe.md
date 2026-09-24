# Informe — Laboratorio 3: MQTT hacia Azure IoT Central

**Curso:** IoT + Cloud + Sistemas Distribuidos — UAB
**Autores:** Juan Felipe Caro, Santiago Cabeza Mendez
**Fecha:** 2026-09-24
**App de IoT Central:** UNAB-Ambiental — Monitoreo de Espacios Académicos
(`laboratorio1caro.azureiotcentral.com`)
**Cómputo:** VM nueva y aislada `laboratorio3caro` (Azure for Students,
`rg-laboratorio3caro`, Mexico Central), creada de 0 para este laboratorio,
sin tocar la máquina compartida del profesor ni VMs de otros compañeros.

## 1. Diagrama del flujo MQTT

```
Dispositivo (SDK / MQTT explícito / Wokwi)
        │  1. DPS: HTTPS + SAS  ->  global.azure-devices-provisioning.net
        │       (idScope + registrationId, token firmado HMAC-SHA256)
        ▼
   DPS responde: IoT Hub asignado
   (iotc-631aa800-...-....azure-devices.net — mismo hub para toda la app)
        │  2. MQTT 3.1.1 sobre TLS 1.2, puerto 8883
        │     CONNECT user={hub}/{deviceId}/?api-version=2021-04-12
        │             pass=SAS(sr={hub}/devices/{deviceId})
        ▼
      IoT Hub  ── PUBLISH devices/{deviceId}/messages/events/ ──►  IoT Central
                  (telemetria: humidity, illuminance, temperature)
        ▲
        └── SUBSCRIBE $iothub/twin/res/#  y  devices/{deviceId}/messages/devicebound/#
            (respuesta de twin y mensajes C2D / comandos)
```

Confirmado con las 3 vías (SDK, MQTT explícito, Wokwi): el "dispositivo" real
de IoT Central nunca habla directo con IoT Central — siempre pasa primero
por DPS (que solo resuelve a qué IoT Hub pertenece) y luego mantiene una
sesión MQTT/TLS persistente contra ese hub. IoT Central es la capa de
aplicación sobre ese mismo IoT Hub.

## 2. Los tres caminos

| Camino | Dónde corre | Qué se ve |
|---|---|---|
| SDK `azure-iot-device` (`sdk_baseline.py`) | VM `laboratorio3caro`, dispositivo `python-vm-01` (mismo del Lab 2) | El SDK esconde topics y token; solo se ve `send_message()`. |
| MQTT explícito (`mqtt_explicito.py`, paho-mqtt) | VM `laboratorio3caro`, dispositivo nuevo `mqtt-explicito-vm` | SAS generado a mano (`dps_sas.py`), topic y QoS explícitos. |
| Arduino/ESP32 (Wokwi) | Wokwi, dispositivo `esp32-wokwi-02` (mismo del Lab 2, firmware sin cambios) | MQTT/TLS a mano en C++ (mismo patrón que `mqtt_explicito.py`). |

Los tres corren sobre la misma app y la misma plantilla del Laboratorio 1/2;
`mqtt-explicito-vm` es un dispositivo nuevo (mismo `id_scope`, misma
plantilla) para poder distinguir sus mensajes en el Data explorer sin
mezclarlos con los del SDK.

## 3. Mediciones (Etapa 3)

CSV crudos en [`../mediciones/`](../mediciones/).

### 3.1 Payload, intervalo y latencia (condiciones normales)

| Camino | Payload (bytes) | Intervalo configurado | Intervalo observado (prom.) | Latencia local (prom.) |
|---|---|---|---|---|
| SDK (`python-vm-01`) | 61 | 10 s | ~10.16 s | ~0.14 s (`send_message`) |
| MQTT explícito QoS 1 | 61 | 10 s | ~10.14 s | ~0.13 s (`wait_for_publish`) |
| MQTT explícito QoS 0 | 61 | 10 s | 10 s | ~0.0003 s (no espera ack) |

El intervalo observado es ~1.5 % mayor que el configurado en ambos casos —
overhead normal de armar el payload y la llamada de red, no un problema del
protocolo. El payload de 61 bytes es fijo porque los 3 valores del modelo
(`humidity`, `illuminance`, `temperature`) siempre se serializan con 1
decimal.

### 3.2 Tiempo hasta verse en IoT Central

En todas las pruebas el mensaje apareció en **Datos sin procesar** dentro
del mismo segundo del publish local (diferencia ≤ 1 s, límite de resolución
de la marca de tiempo que muestra el portal). No hay retraso perceptible
entre el `PUBACK` del hub y la visibilidad en la app.

### 3.3 Corte de red de ~20 s

Se cortó el tráfico saliente al puerto 8883 con `iptables -A OUTPUT -p tcp
--dport 8883 -j DROP` durante 20 s mientras cada cliente publicaba, y se
restauró. Log completo en
[`../mediciones/sdk_cutoff.log`](../mediciones/sdk_cutoff.log) y
[`../mediciones/mqtt_cutoff.log`](../mediciones/mqtt_cutoff.log).

| Camino | Qué pasó durante el corte | Recuperación |
|---|---|---|
| SDK | El `send_message()` que coincidió con el corte tardó 16.09 s en vez de ~0.14 s (bloqueado esperando el ack); no hubo excepción ni reconexión visible en el log (una sola línea "Conectado"). | Automática: siguiente publish salió ~16 s más tarde de lo normal y luego el intervalo volvió a 10 s. |
| MQTT explícito | El publish que coincidió con el corte agotó el timeout de `wait_for_publish(10 s)` sin confirmar (`latencia_publish_local_s=10.0015`); el script igual siguió su loop. | Automática: `loop_start()` de paho-mqtt corre `loop_forever()` internamente, que reintenta a nivel de socket. El siguiente publish, ~20 s después (duración exacta del corte), volvió a completarse en ~0.14 s normales. |

**Hallazgo:** un `DROP` de firewall (paquetes descartados en silencio, sin
`RST`) no genera un ciclo completo de "MQTT disconnect → reconnect" en
ninguno de los dos clientes — ambos lo toleran a nivel de socket/TCP, con un
pico de latencia proporcional a la duración del corte, sin perder mensajes
ni requerir intervención manual. Esto es distinto de una desconexión real de
red (p. ej. WiFi caído), donde sí se esperaría ver un `CONNACK` nuevo — ese
es justamente el ciclo `Conectado ↔ Desconectado` que se observa en Wokwi
cuando el gateway IoT de Wokwi se reinicia.

### 3.4 QoS 0, 1 y 2

CSV: [`../mediciones/mediciones_qos.csv`](../mediciones/mediciones_qos.csv).

| QoS pedido | Resultado | Latencia local |
|---|---|---|
| 0 | Aceptado. "Fire and forget": el cliente no espera nada del broker. | ~0.0003 s |
| 1 | Aceptado. Espera `PUBACK`. | ~0.13 s |
| 2 | Aceptado **sin error**, pero con latencia prácticamente idéntica a QoS 1 (~0.13–0.14 s), no el handshake completo de 4 pasos (`PUBREC`/`PUBREL`/`PUBCOMP`) que exige la especificación MQTT para QoS 2. | ~0.13 s |

**Conclusión de QoS:** el comportamiento observado confirma lo documentado
por Microsoft: **IoT Hub/Central soporta QoS 0 y QoS 1, pero no implementa
QoS 2** — en vez de rechazar la conexión o el publish, lo degrada
silenciosamente a un comportamiento equivalente a QoS 1 (una sola
confirmación, sin el handshake extendido). Para este escenario (telemetría
ambiental cada 10 s, sin transacciones críticas) **QoS 1 es la opción
correcta**: garantiza al menos una entrega sin el costo de latencia de un
handshake que, de todas formas, el hub no ofrece.

## 4. Comparación y conclusión

Ver tabla completa en [`../comparativa.md`](../comparativa.md).

El SDK es la opción por defecto para cualquier dispositivo que corra Python
(o cualquier lenguaje con SDK oficial) en un sistema con recursos
suficientes: DPS, renovación de tokens SAS, reconexión y keep-alive quedan
resueltos por una librería mantenida por Microsoft, y el código de
aplicación se reduce a llamar `send_message()`. Un cliente MQTT explícito
tiene sentido en dos escenarios concretos: (1) cuando la plataforma no tiene
SDK oficial de Azure (como un ESP32 en Arduino/C++, donde no existe ya un
SDK activamente mantenido) y (2) cuando se necesita control fino del
protocolo — elegir QoS por mensaje, inspeccionar el token SAS real, o
depurar exactamente qué topic MQTT está fallando — algo que el SDK
deliberadamente esconde. El precio de ese control es más código (en este
laboratorio, `dps_sas.py` + `mqtt_explicito.py` reimplementan a mano lo que
el SDK da en dos líneas) y la responsabilidad de manejar reconexión y
renovación de tokens uno mismo, aunque en este caso paho-mqtt ya trae esa
lógica integrada en `loop_start()`.

## 5. Evidencias

Ver [`../evidencias/`](../evidencias/): capturas del Data explorer /
Datos sin procesar para `python-vm-01`, `mqtt-explicito-vm` y
`esp32-wokwi-02` mostrando telemetría real y, en el caso de Wokwi, el ciclo
`Conectado ↔ Desconectado`.
