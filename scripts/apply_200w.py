#!/usr/bin/env python3
"""Aplicar power limit 200W correctamente via SSH."""
import paramiko
import sys
import time

HOST = "100.103.141.33"
USER = "pepe"
PASS = "pepe1234"

def run_sudo(ssh, cmd, timeout=30):
    """Ejecuta comando con sudo usando password via stdin."""
    print(f"\n>>> sudo {cmd}")
    full_cmd = f"sudo -S {cmd}"
    stdin, stdout, stderr = ssh.exec_command(full_cmd, timeout=timeout)
    stdin.write(PASS + "\n")
    stdin.flush()
    out = stdout.read().decode()
    err = stderr.read().decode()
    exit_code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip())
    if err.strip() and "password" not in err.lower():
        print(f"[STDERR] {err.strip()}")
    print(f"[EXIT: {exit_code}]")
    return out, err, exit_code

def run_cmd(ssh, cmd, timeout=15):
    """Ejecuta comando sin sudo."""
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    exit_code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip())
    if err.strip():
        print(f"[STDERR] {err.strip()}")
    print(f"[EXIT: {exit_code}]")
    return out, err, exit_code

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)
    print("✅ Conectado")
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

# 1. Habilitar persistence mode (necesario para power limit persistente)
print("\n" + "="*50)
print("1. HABILITANDO PERSISTENCE MODE")
print("="*50)
run_sudo(ssh, "nvidia-smi -pm 1")

# 2. Verificar
run_cmd(ssh, "nvidia-smi --query-gpu=persistence_mode --format=csv,noheader")

# 3. Aplicar power limit 200W
print("\n" + "="*50)
print("2. APLICANDO POWER LIMIT 200W")
print("="*50)
run_sudo(ssh, "nvidia-smi -pl 200")

# 4. Verificar power limit
print("\n" + "="*50)
print("3. VERIFICANDO POWER LIMIT")
print("="*50)
run_cmd(ssh, "nvidia-smi --query-gpu=power.limit,power.default,power.draw,temperature.gpu --format=csv")

# 5. Verificar estado general
run_cmd(ssh, "nvidia-smi")

print("\n✅ Done!")
ssh.close()
