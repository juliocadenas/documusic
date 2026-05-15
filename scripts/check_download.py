"""Check if ACE-Step model download completed and backend is up."""
import paramiko

HOST = "100.103.141.33"
USER = "pepe"
PASS = "pepe1234"

def run(ssh, cmd, timeout=120):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip(): print(out.strip()[-3000:])
    if err.strip(): print(f"STDERR: {err.strip()[-2000:]}")
    return out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)

# Check backend status
run(ssh, 'curl -s http://localhost:8000/ 2>&1')

# Check logs for download progress
run(ssh, "docker logs documusic_backend --tail 30 2>&1")

# Check if model dir exists
run(ssh, "docker exec documusic_backend ls -la /app/models/ACE-Step-v1-3.5B/ 2>&1")

ssh.close()
print("\nDone!")
