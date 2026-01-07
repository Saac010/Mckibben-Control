import paho.mqtt.client as mqtt
import json
import time
import threading
import sys

# ======================================================
# CONFIGURACIÓN HIVEMQ (MODO WEBSOCKETS - EL QUE PASA FIREWALLS)
# ======================================================
# 1. Tu Cluster (SIN http:// ni mqtt://)
MQTT_BROKER = "e56647093f1949248358d14fc9d9b917.s1.eu.hivemq.cloud"
# 2. El puerto DEBE ser 8884 para WebSockets (PythonAnywhere lo exige)
MQTT_PORT = 8883
# 3. Tus credenciales
MQTT_USER = "esp32"
MQTT_PASS = "Clave1234"

TOPIC_DATOS = "mckibben/datos"
TOPIC_CMD   = "mckibben/cmd"

# ======================================================
# CLIENTE MQTT
# ======================================================
class MQTTClientHandler:
    def __init__(self):
        print("[SISTEMA] Inicializando Cliente MQTT...", file=sys.stderr)
        
        # --- CORRECCIÓN VITAL PARA PAHO-MQTT 2.0 ---
        # Usamos CallbackAPIVersion.VERSION1 para evitar errores de compatibilidad
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, transport='websockets')
        except AttributeError:
            # Si es una versión vieja de paho, usamos la forma antigua
            self.client = mqtt.Client(transport='websockets')

        # Configuración para HiveMQ Cloud (WebSockets)
        self.client.ws_set_options(path="/mqtt")
        
        # Seguridad SSL (Obligatoria)
        self.client.tls_set()
        self.client.username_pw_set(MQTT_USER, MQTT_PASS)

        # Asignar funciones
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        
        self.connected = False
        self.data_buffer = []
        self.latest_vals = (0.0, 0.0, 0.0, 0.0, 0.0) 
        self.lock = threading.Lock()

        # Conectar
        try:
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.client.loop_start()
        except Exception as e:
            print(f"[ERROR CRÍTICO] No se pudo conectar al Broker: {e}", file=sys.stderr)

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("[EXITO] ¡CONECTADO A HIVEMQ!", file=sys.stderr)
            self.connected = True
            client.subscribe(TOPIC_DATOS)
        else:
            errores = {
                1: "Protocolo incorrecto",
                2: "ID Cliente inválido",
                3: "Servidor no disponible",
                4: "Usuario/Password incorrectos",
                5: "No autorizado"
            }
            msg = errores.get(rc, f"Código desconocido {rc}")
            print(f"[ERROR] Conexión rechazada: {msg}", file=sys.stderr)
            self.connected = False

    def on_disconnect(self, client, userdata, rc):
        print("[AVISO] Desconectado del Broker", file=sys.stderr)
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
        except Exception as e:
            print(f"[ERROR DATOS] {e}", file=sys.stderr)

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

# Instancia Global
mqtt_handler = MQTTClientHandler()

# FUNCIONES PUENTE
def get_sensor_buffer(): return mqtt_handler.get_buffer()
def send_tcp_command(msg): return mqtt_handler.send_cmd(msg)
def is_esp_connected(): return mqtt_handler.connected
def purge_buffer(): mqtt_handler.clear_buffer()
def set_target_ip(ip): pass
