import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

WATCHDOG_SCRIPT = """#!/usr/bin/env python3
import subprocess
import time
import datetime

# RTX 5080 tiene 16303 MB utiles. Ponemos el limite en 15300 MB (93%)
MAX_VRAM_MB = 15300 

def log(msg):
    with open("/var/log/gpu_watchdog.log", "a") as f:
        f.write(f"[{datetime.datetime.now()}] {msg}\\n")

log("Iniciando GPU Watchdog para DocuMusic...")

while True:
    try:
        res = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            text=True
        )
        mem_used = int(res.strip())
        
        if mem_used > MAX_VRAM_MB:
            log(f"¡PELIGRO! VRAM en {mem_used}MB. Supera el limite de {MAX_VRAM_MB}MB.")
            log("Reiniciando contenedor documusic_backend para salvar la GPU...")
            subprocess.run(["docker", "restart", "documusic_backend"])
            log("Contenedor reiniciado. Esperando 15 segundos para estabilizar.")
            time.sleep(15)
            
    except Exception as e:
        pass
    
    time.sleep(0.5) # Monitoreo cada medio segundo
"""

SERVICE_FILE = """[Unit]
Description=DocuMusic GPU Memory Watchdog
After=docker.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/gpu_watchdog.py
Restart=always
User=root

[Install]
WantedBy=multi-user.target
"""

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(f"echo {PASS} | sudo -S bash -c '{cmd}'")
    return stdout.read().decode('utf-8')

print("Instalando Watchdog...")
# Subir script
client.exec_command(f"cat << 'EOF' > /tmp/gpu_watchdog.py\n{WATCHDOG_SCRIPT}\nEOF")
run("mv /tmp/gpu_watchdog.py /opt/gpu_watchdog.py")
run("chmod +x /opt/gpu_watchdog.py")

# Subir servicio
client.exec_command(f"cat << 'EOF' > /tmp/gpu_watchdog.service\n{SERVICE_FILE}\nEOF")
run("mv /tmp/gpu_watchdog.service /etc/systemd/system/documusic-watchdog.service")

# Habilitar
run("systemctl daemon-reload")
run("systemctl enable --now documusic-watchdog.service")
print("Watchdog instalado y corriendo.")

client.close()
