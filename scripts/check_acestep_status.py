"""Check ACE-Step deployment status."""
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
    if out.strip(): print(out.strip()[-3000:])
    if err.strip(): print(f"STDERR: {err.strip()[-1000:]}")
    return out

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)

# Check container status
run(ssh, "docker ps --filter name=documusic_backend --format '{{.Status}}'")

# Check full startup logs
run(ssh, "docker logs documusic_backend 2>&1 | tail -50")

# Check ACE-Step directory
run(ssh, "ls -la /home/pepe/AI_MODELS/ace-step/ 2>/dev/null")

# Check if API is ready
run(ssh, "curl -s http://localhost:8000/ 2>&1 | head -5")

ssh.close()
