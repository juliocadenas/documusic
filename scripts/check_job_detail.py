"""Detailed job status check with backend logs."""
import paramiko
import json

def run(ssh, cmd, timeout=15):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return out + ("\nSTDERR: " + err if err else "")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.103.141.33", username="pepe", password="pepe1234")

job_id = "dbee957c"

# Get full job status
status_raw = run(ssh, f"curl -s http://localhost:8000/api/job/{job_id}")
try:
    job = json.loads(status_raw)
    print(f"Status: {job.get('status')}")
    print(f"Audio URL: {job.get('audio_url')}")
    print(f"Error: {job.get('error')}")
    logs = job.get('logs', [])
    print(f"\nLogs ({len(logs)} lines):")
    for log in logs[-20:]:
        print(f"  {log}")
except:
    print(f"Raw status: {status_raw[:500]}")

# GPU
gpu = run(ssh, "nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader")
print(f"\nGPU: {gpu}")

# Backend logs (last 20 lines)
print("\n=== BACKEND LOGS (last 20) ===")
logs = run(ssh, "docker logs documusic_backend --tail 20 2>&1")
print(logs)

ssh.close()
