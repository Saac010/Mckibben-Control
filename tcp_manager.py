import socket
import threading
import time
import json 

# Configuración Inicial
ESP_IP = "192.168.1.x" 
ESP_PORT = 5000

class ESP32Client:
    def __init__(self):
        self.sock = None
        self.running = False
        self.lock = threading.Lock()
        self.data_buffer = []  
        self.latest_vals = (0.0, 0.0, 0.0, 0.0, 0.0)
        self.connected = False
        self.thread = threading.Thread(target=self._background_listener)
        self.thread.daemon = True 
        self.thread.start()

    def set_ip(self, ip):
        global ESP_IP
        if ESP_IP != ip:
            ESP_IP = ip
            self.disconnect() 

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(2) 
            self.sock.connect((ESP_IP, ESP_PORT))
            self.sock.settimeout(None) 
            self.connected = True
        except:
            self.connected = False

    def disconnect(self):
        if self.sock:
            try: self.sock.close()
            except: pass
        self.sock = None
        self.connected = False

    def _background_listener(self):
        self.running = True
        while self.running:
            if not self.connected:
                self.connect()
                time.sleep(2)
                continue
            try:
                f = self.sock.makefile('r', encoding='utf-8', errors='ignore')
                while self.connected:
                    line = f.readline()
                    if not line: break 
                    self._parse_data(line)
            except: pass
            finally:
                self.disconnect()
                time.sleep(1)

    def _parse_data(self, line):
        line = line.strip()
        if not line: return
        try:
            if line.startswith("{") and line.endswith("}"):
                data = json.loads(line)
                with self.lock:
                    vals = (
                        float(data.get('f', 0)),
                        float(data.get('l', 0)),
                        float(data.get('p', 0)),
                        float(data.get('a', 0)),
                        float(data.get('pwm', 0))
                    )
                    self.data_buffer.append(vals)
                    self.latest_vals = vals
        except: pass

    def get_buffer(self):
        with self.lock:
            if not self.data_buffer:
                return [], self.latest_vals
            chunk = list(self.data_buffer)
            self.data_buffer.clear()
            return chunk, self.latest_vals

    def get_single_data(self):
        with self.lock:
            return self.latest_vals

    def clear_internal_buffer(self):
        with self.lock:
            self.data_buffer.clear() 

    def send_command(self, message):
        if not self.connected or not self.sock: return False
        try:
            msg = f"{message}\n"
            self.sock.sendall(msg.encode())
            return True
        except:
            self.disconnect()
            return False

client_instance = ESP32Client()

# FUNCIONES PUENTE
def set_target_ip(ip): client_instance.set_ip(ip)
def is_esp_connected(): return client_instance.connected
def send_tcp_command(msg): return client_instance.send_command(msg)
def get_sensor_buffer(): return client_instance.get_buffer()
def get_sensor_data(): return client_instance.get_single_data()

# --- NUEVO PUENTE PARA APP.PY ---
def purge_buffer(): client_instance.clear_internal_buffer()