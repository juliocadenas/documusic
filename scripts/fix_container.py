"""Fix read-only container by recreating it."""
import paramiko
import time

def run(ssh, cmd, timeout=60):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if err:
        print(f"  STDERR: {err[:200]}")
    return out

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.103.141.33", username="pepe", password="pepe1234")

# 1. Check if host filesystem is writable
print("=== HOST WRITE TEST ===")
print(run(ssh, "touch /tmp/test_write && echo 'HOST OK' && rm /tmp/test_write"))

# 2. Stop and recreate container
print("\n=== RECREATING CONTAINER ===")
print(run(ssh, "cd ~/documusic && docker-compose down", timeout=30))
print(run(ssh, "cd ~/documusic && docker-compose up -d", timeout=60))

# 3. Wait for backend
print("\n=== WAITING FOR BACKEND ===")
for i in range(30):
    time.sleep(2)
    out = run(ssh, "curl -s http://localhost:8000/ | head -1", timeout=5)
    if '"status"' in out:
        print(f"Backend UP after {i*2}s")
        break
else:
    print("FAILED to start!")
    ssh.close()
    exit(1)

# 4. Verify container write
print("\n=== WRITE TEST (container) ===")
print(run(ssh, "docker exec documusic_backend bash -c 'touch /app/outputs/test_write && echo WRITE_OK && rm /app/outputs/test_write' 2>&1"))

# 5. Check backend status
print("\n=== STATUS ===")
print(run(ssh, "curl -s http://localhost:8000/"))

ssh.close()
