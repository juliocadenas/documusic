#!/usr/bin/env python3
"""Install bitsandbytes in the Docker container."""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234', timeout=15)

def run(cmd, timeout=120):
    print(f">>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip(): print(out.strip()[-500:])
    if err.strip(): print(f"[ERR] {err.strip()[-500:]}")

# Install bitsandbytes
run("docker exec documusic_backend pip install bitsandbytes", timeout=180)

# Verify
run('docker exec documusic_backend python3 -c "import bitsandbytes as bnb; print(f\"bitsandbytes {bnb.__version__}\")"', timeout=30)

# Quick test: can we create a quantized model config?
run('docker exec documusic_backend python3 -c "from transformers import BitsAndBytesConfig; cfg = BitsAndBytesConfig(load_in_8bit=True); print(cfg)"', timeout=30)

ssh.close()
