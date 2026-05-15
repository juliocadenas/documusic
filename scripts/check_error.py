"""Get full error details for failed job."""
import paramiko
import json

def run(ssh, cmd, timeout=15):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode().strip()

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.103.141.33", username="pepe", password="pepe1234")

# Get full job status
status = run(ssh, "curl -s http://localhost:8000/api/job/030f8349")
try:
    data = json.loads(status)
    print(f"Status: {data.get('status')}")
    print(f"Audio URL: {data.get('audio_url')}")
    print(f"\nLogs ({len(data.get('logs', []))} lines):")
    for log in data.get('logs', [])[-30:]:
        print(f"  {log}")
except Exception as e:
    print(f"Raw: {status[:2000]}")

# Check GPU
gpu = run(ssh, "nvidia-smi --query-gpu=memory.used --format=csv,noheader")
print(f"\nGPU: {gpu} MiB")

ssh.close()
