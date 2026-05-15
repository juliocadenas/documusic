"""Check current generation progress."""
import paramiko

HOST = "100.103.141.33"
USER = "pepe"
PASS = "pepe1234"

def run(ssh, cmd, timeout=30):
    print(f">>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip():
        print(out.strip()[-3000:])
    if err.strip():
        print(f"STDERR: {err.strip()[-500:]}")
    return out

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)

# Check job status
import json
out = run(ssh, "curl -s http://localhost:8000/api/job/9b7b5def 2>&1")
try:
    job = json.loads(out)
    print(f"\n{'='*60}")
    print(f"STATUS: {job.get('status')}")
    print(f"COMPLETED: {job.get('completed_variants')}/{job.get('num_variants')}")
    print(f"AUDIO URL: {job.get('audio_url')}")
    logs = job.get('logs', [])
    print(f"\nLAST 10 LOGS:")
    for log in logs[-10:]:
        print(f"  {log}")
    print(f"{'='*60}")
except:
    pass

# Check if infer.py is still running
run(ssh, "docker exec documusic_backend ps aux | grep infer.py | grep -v grep")

# Check output files
run(ssh, "docker exec documusic_backend find /app/outputs -type f 2>/dev/null | head -20")

# Check GPU
run(ssh, "nvidia-smi --query-gpu=memory.used,power.draw --format=csv,noheader 2>&1")

ssh.close()
