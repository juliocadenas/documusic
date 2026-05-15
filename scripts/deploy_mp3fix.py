#!/usr/bin/env python3
"""Deploy: git pull + restart backend on server."""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234', timeout=15)
print("✅ Conectado")

def run(cmd, timeout=60):
    print(f">>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip(): print(out.strip())
    if err.strip(): print(f"[ERR] {err.strip()}")

# 1. Git pull
run("cd ~/documusic && git pull")

# 2. Restart backend
run("cd ~/documusic && docker compose restart documusic_backend", timeout=60)

# 3. Wait and check
print("\nEsperando 10s...")
time.sleep(10)
run("docker logs --tail 15 documusic_backend 2>&1")

# 4. Verify endpoint
run("curl -s http://localhost:8000/ | python3 -c 'import sys,json; d=json.load(sys.stdin); print(f\"Status: {d[\"status\"]}, yue_ready: {d[\"yue_ready\"]}\")'")

# 5. Verify power limit
run("nvidia-smi --query-gpu=power.limit,power.draw --format=csv,noheader")

print("\n✅ Deploy completado")
ssh.close()
