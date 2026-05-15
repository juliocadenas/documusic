"""Restart backend container directly."""
import paramiko
import time

HOST = "100.103.141.33"
USER = "pepe"
PASS = "pepe1234"

def run(ssh, cmd, timeout=120):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip(): print(out.strip()[-2000:])
    if err.strip(): print(f"STDERR: {err.strip()[-1500:]}")
    return out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)

# Restart container directly
run(ssh, "docker restart documusic_backend 2>&1")

# Wait
print("\nWaiting for backend...")
time.sleep(10)

# Check
run(ssh, 'curl -s http://localhost:8000/ 2>&1')

# Check logs
run(ssh, "docker logs documusic_backend --tail 25 2>&1")

ssh.close()
print("\nDone!")
