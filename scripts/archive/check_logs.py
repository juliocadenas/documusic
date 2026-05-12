import paramiko
import sys

# Forzar salida UTF-8 en Windows
sys.stdout.reconfigure(encoding='utf-8')

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

stdin, stdout, stderr = client.exec_command("docker logs documusic_backend 2>&1")
logs = stdout.read().decode('utf-8')

print("--- PROGRESO DE GENERACIÓN YUE ---")
relevant_lines = []
for line in logs.split('\n'):
    if any(k in line for k in ["Stage", "inference", "%", "Loading", "it/s"]):
        relevant_lines.append(line)

# Mostrar las ultimas 20 lineas relevantes
for line in relevant_lines[-20:]:
    print(line)

client.close()
