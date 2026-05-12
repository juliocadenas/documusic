"""Verifica el resultado de la generacion."""
import paramiko
import json
import time

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

def run(client, cmd, timeout=30):
    _, o, e = client.exec_command(cmd, timeout=timeout)
    return o.read().decode("utf-8", errors="replace")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=15)

# Wait 10 minutes for full generation
print("Esperando 10 minutos para generacion completa...")
time.sleep(600)

# Get all jobs by trying the latest
# First check what jobs exist
out = run(c, "curl -s http://localhost:8000/api/diagnostics 2>&1")
print(f"Server status: {out[:200]}")

# Check docker logs for completion
out = run(c, "docker logs documusic_backend --tail 30 2>&1")
print(f"\nDocker logs:\n{out[:2000]}")

# Check output files
out = run(c, "docker exec documusic_backend find /app/outputs -name '*.mp3' -newer /app/outputs -mmin -15 2>&1")
print(f"\nRecent MP3 files:\n{out[:500]}")

out = run(c, "docker exec documusic_backend find /app/outputs -name '*.wav' -mmin -15 2>&1")
print(f"\nRecent WAV files:\n{out[:500]}")

c.close()
print("\nDone.")
