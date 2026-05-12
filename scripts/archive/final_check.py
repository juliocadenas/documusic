"""Verifica el resultado final de la generacion."""
import paramiko
import json

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

def run(client, cmd, timeout=30):
    _, o, e = client.exec_command(cmd, timeout=timeout)
    return o.read().decode("utf-8", errors="replace")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=15)

# Check all recent jobs
out = run(c, "curl -s http://localhost:8000/api/job/233433fc 2>&1")
try:
    data = json.loads(out)
    status = data.get("status")
    print(f"Job 233433fc Status: {status}")

    if status == "done":
        print(f"Audio URL: http://{HOST}:8000{data.get('audio_url')}")
    elif status == "error":
        print(f"Error: {data.get('error')}")
        print(f"Detail: {data.get('error_detail', '')[:500]}")
    else:
        logs = data.get("logs", [])
        print(f"Logs ({len(logs)}):")
        for log in logs[-10:]:
            print(f"  > {log[:150]}")
except:
    print(f"Raw: {out[:500]}")

# Check docker logs for final status
print("\nDocker logs (tail 20):")
out = run(c, "docker logs documusic_backend --tail 20 2>&1")
print(out[:2000])

# Check output files
print("\nOutput files:")
out = run(c, "docker exec documusic_backend ls -la /app/outputs/ 2>&1")
print(out[:500])

c.close()
