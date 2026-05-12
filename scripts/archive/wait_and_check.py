"""Espera y verifica el resultado final de la generacion."""
import paramiko
import json
import time

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"
JOB_ID = "233433fc"

def run(client, cmd, timeout=30):
    _, o, e = client.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    return out

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=15)

# Wait 5 minutes for stage 2 to complete
print("Esperando 5 minutos para Stage 2...")
time.sleep(300)

# Check job status
out = run(c, "curl -s http://localhost:8000/api/job/" + JOB_ID + " 2>&1")
try:
    data = json.loads(out)
    status = data.get("status", "unknown")
    print(f"Status: {status}")

    if status == "done":
        audio_url = data.get("audio_url", "")
        print(f"CANCION GENERADA!")
        print(f"Audio URL: http://{HOST}:8000{audio_url}")
    elif status == "error":
        print(f"ERROR: {data.get('error', '')}")
        print(f"Detail: {data.get('error_detail', '')[:500]}")
    else:
        print(f"Still {status}...")
        logs = data.get("logs", [])
        for log in logs[-5:]:
            print(f"  > {log[:150]}")

        # Check docker logs
        docker_logs = run(c, "docker logs documusic_backend --tail 30 2>&1")
        print(f"\nDocker logs:\n{docker_logs[:2000]}")
except:
    print(f"Raw: {out[:500]}")

c.close()
