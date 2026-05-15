"""Deploy ACE-Step API fix to server: git pull + restart backend."""
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

# 1. Git pull
run(ssh, "cd ~/documusic && git pull 2>&1")

# 2. Restart backend (volume mount means code is live)
run(ssh, "cd ~/documusic && docker compose restart backend 2>&1")

# 3. Wait for backend
print("\nWaiting for backend...")
time.sleep(8)

# 4. Check backend
run(ssh, 'curl -s http://localhost:8000/ 2>&1')

# 5. Check startup logs
run(ssh, "docker logs documusic_backend --tail 20 2>&1")

ssh.close()
print("\nDone!")
