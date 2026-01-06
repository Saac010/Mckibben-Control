import paho.mqtt.client as mqtt
import json
import time
import threading

# ======================================================
# CONFIGURACIÓN HIVEMQ (MODO WEBSOCKETS PARA PYTHONANYWHERE)
# ======================================================
MQTT_BROKER = "e56647093f1949248358d14fc9d9b917.s1.eu.hivemq.cloud"
MQTT_PORT = 8884                             # <--- CAMBIO 1: Puerto WSS (Suele ser 8884)
MQTT_USER = "esp32"
MQTT_PASS = "Clave1234"

TOPIC_DATOS = "mckibben/datos"
TOPIC_CMD   = "mckibben/cmd"

# ======================================================
# CLIENTE MQTT
# ======================================================
class MQTTClientHandler:
    def __init__(self):
        # <--- CAMBIO 2: Activamos 'websockets' para burlar el firewall
        self.client = mqtt.Client(transport='websockets')

        # <--- CAMBIO 3: Ruta específica de HiveMQ
        self.client.ws_set_options(path="/mqtt")

        self.client.tls_set() # SSL es obligatorio
        self.client.username_pw_set(MQTT_USER, MQTT_PASS)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.connected = False
        self.data_buffer = []
        self.latest_vals = (0.0, 0.0, 0.0, 0.0, 0.0)
        self.lock = threading.Lock()

        try:
            # Conexión con keepalive de 60s
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.client.loop_start()
        except Exception as e:
            print(f"[ERROR MQTT] {e}")

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("[SISTEMA] Conectado a HiveMQ Cloud (Vía WebSockets)!")
            self.connected = True
            client.subscribe(TOPIC_DATOS)
        else:
            print(f"[ERROR] Fallo conexión MQTT, código: {rc}")
            self.connected = False

    def on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode()
            data = json.loads(payload)
            vals = (
                float(data.get('f', 0)),
                float(data.get('l', 0)),
                float(data.get('p', 0)),
                float(data.get('a', 0)),
                float(data.get('pwm', 0))
            )
            with self.lock:
                self.data_buffer.append(vals)
                self.latest_vals = vals
        except:
            pass

    def get_buffer(self):
        with self.lock:
            if not self.data_buffer:
                return [], self.latest_vals
            chunk = list(self.data_buffer)
            self.data_buffer.clear()
            return chunk, self.latest_vals

    def clear_buffer(self):
        with self.lock:
            self.data_buffer.clear()

    def send_cmd(self, msg):
        if self.connected:
            self.client.publish(TOPIC_CMD, str(msg))
            return True
        return False

mqtt_handler = MQTTClientHandler()

# FUNCIONES PUENTE
def get_sensor_buffer(): return mqtt_handler.get_buffer()
def send_tcp_command(msg): return mqtt_handler.send_cmd(msg)
def is_esp_connected(): return mqtt_handler.connected
def purge_buffer(): mqtt_handler.clear_buffer()
def set_target_ip(ip): pass