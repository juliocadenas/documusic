#!/usr/bin/env python3
"""Verificar power limit de la GPU en el servidor."""
import paramiko
import sys

HOST = "100.103.141.33"
USER = "pepe"
PASS = "pepe1234"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)
except Exception as e:
    print(f"❌ No se pudo conectar: {e}")
    sys.exit(1)

# Verificar power limit
print("=== POWER LIMIT ACTUAL ===")
stdin, stdout, stderr = ssh.exec_command("nvidia-smi --query-gpu=power.limit,power.draw,temperature.gpu,memory.used --format=csv", timeout=15)
print(stdout.read().decode())
print(stderr.read().decode())

# Verificar si es persistente
print("=== PERSISTENCE MODE ===")
stdin, stdout, stderr = ssh.exec_command("nvidia-smi --query-gpu=persistence_mode --format=csv,noheader", timeout=15)
print(stdout.read().decode())

ssh.close()
