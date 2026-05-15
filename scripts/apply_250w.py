#!/usr/bin/env python3
"""Aplicar power limit 250W (mínimo de RTX 5080) via SSH."""
import paramiko
import sys

HOST = "100.103.141.33"
USER = "pepe"
PASS = "pepe1234"

def run_sudo(ssh, cmd, timeout=30):
    print(f">>> sudo {cmd}")
    stdin, stdout, stderr = ssh.exec_command(f"sudo -S {cmd}", timeout=timeout)
    stdin.write(PASS + "\n")
    stdin.flush()
    out = stdout.read().decode()
    err = stderr.read().decode()
    exit_code = stdout.channel.recv_exit_status()
    if out.strip(): print(out.strip())
    if err.strip() and "password" not in err.lower() and "contraseña" not in err.lower():
        print(f"[STDERR] {err.strip()}")
    print(f"[EXIT: {exit_code}]")
    return out, err, exit_code

def run_cmd(ssh, cmd, timeout=15):
    print(f">>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip(): print(out.strip())
    if err.strip(): print(f"[STDERR] {err.strip()}")
    return out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)
print("✅ Conectado\n")

# Aplicar 250W (mínimo permitido)
print("Aplicando power limit 250W (mínimo RTX 5080)...")
run_sudo(ssh, "nvidia-smi -pl 250")

# Verificar
print("\nVerificando...")
run_cmd(ssh, "nvidia-smi --query-gpu=power.limit,power.draw,temperature.gpu,memory.used --format=csv")

# Ver nvidia-smi completo
run_cmd(ssh, "nvidia-smi")

print("\n✅ Power limit 250W aplicado")
print("🚀 Listo para probar generación desde el frontend")
ssh.close()
