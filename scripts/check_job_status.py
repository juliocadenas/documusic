"""Check job status and backend connectivity."""
import paramiko
import time

HOST = "100.103.141.33"
USER = "pepe"
PASS = "pepe1234"

def run(ssh, cmd, timeout=30):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip():
        print(out.strip()[-3000:])
    if err.strip():
        print(f"STDERR: {err.strip()[-1000:]}")
    return out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)
print(f"✅ Connected to {HOST}")

# Check if port 8000 is listening
run(ssh, "ss -tlnp | grep 8000")

# Check docker port mapping
run(ssh, "docker port documusic_backend")

# Check job status via curl from server itself
run(ssh, "curl -s http://localhost:8000/api/job/9b7b5def 2>&1 | head -50")

# Check if inference subprocess is still running
run(ssh, "docker exec documusic_backend ps aux | grep -E 'infer.py|python' | head -10")

# Check recent backend logs with timestamps
run(ssh, "docker logs documusic_backend --tail 80 2>&1 | grep -E 'ERROR|WARN|Stage|inference|variant|complete|failed|Traceback|Error' | tail -30")

# Check GPU processes
run(ssh, "nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv,noheader 2>&1")

# Check if there are output files
run(ssh, "docker exec documusic_backend find /tmp -name '*.wav' -o -name '*.mp3' 2>/dev/null | head -20")

ssh.close()
print("\n✅ Done!")
