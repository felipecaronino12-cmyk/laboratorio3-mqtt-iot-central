# Comparación: SDK Python vs MQTT explícito vs Wokwi Arduino

| Criterio | SDK `azure-iot-device` | MQTT explícito (paho-mqtt) | Wokwi Arduino (MQTT/TLS a mano) |
|---|---|---|---|
| Facilidad de implementación | Alta: `create_from_symmetric_key` + `connect()` + `send_message()`. DPS y renovación de token quedan ocultos. | Media: hay que escribir la firma SAS (`dps_sas.py`), el polling de DPS y los topics a mano, pero en Python es directo. | Baja: todo lo anterior pero en C++, con HMAC/base64 manuales vía `mbedtls`, sin SDK oficial de Azure para Arduino. |
| Control del protocolo | Ninguno — topics, QoS y tokens están escondidos. | Total — se elige QoS por mensaje, se ve el token SAS real, se decide el topic exacto. | Total, igual que el MQTT explícito en Python. |
| Payload | 61 bytes (JSON con los 3 valores del modelo). | 61 bytes, idéntico. | 61 bytes, idéntico (mismo esquema JSON). |
| Latencia percibida (envío) | ~0.14 s normal; picos de hasta 16 s ante corte de red de 20 s. | ~0.13 s en QoS 1; ~0.0003 s en QoS 0 (sin ack). | Comparable en la práctica (mismo transporte MQTT/TLS); no medida en detalle por la lentitud del emulador en este entorno. |
| Reconexión ante corte de ~20 s | Automática, sin código adicional: la llamada bloqueada se resuelve sola cuando vuelve la red. | Automática también: `loop_start()` de paho-mqtt corre `loop_forever()` internamente, que reintenta a nivel de socket sin que el código de la aplicación haga nada. | En Lab 2 se observó un ciclo real `Conectado ↔ Desconectado` en el historial de IoT Central (reinicio del gateway de Wokwi), a diferencia del "blackhole" simulado aquí con `iptables DROP`. |
| Utilidad para el escenario del Lab 1 (flota de aulas) | La mejor opción si todos los nodos de código corren en un SO con Python/.NET/Java/etc.: menos código, menos superficie de error. | Útil como capa de depuración/diagnóstico, o si se necesita QoS 0 para telemetría de alta frecuencia sin esperar ack. | Obligatorio para el nodo embebido real (ESP32): no existe alternativa con SDK oficial de Azure para Arduino, así que este es el único camino posible en hardware real de bajo nivel. |

**Conclusión accionable:** para un nodo que corre en una VM o servidor con un
lenguaje soportado por el SDK oficial, usar siempre el SDK — resuelve DPS,
renovación de tokens y reconexión sin código adicional, y el "costo" de no
controlar el protocolo no aplica en un escenario de telemetría estándar como
el del Laboratorio 1. Reservar un cliente MQTT explícito para: (a)
plataformas sin SDK oficial (firmware embebido tipo el ESP32 de Wokwi, donde
es la única opción), o (b) depuración puntual cuando hay que confirmar
exactamente qué token, topic o código de error está devolviendo el broker —
algo que el SDK oculta a propósito.
