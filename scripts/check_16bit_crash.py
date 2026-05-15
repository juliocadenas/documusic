"""Check server status after 16-bit generation crash."""
import paramiko, time

def run(ssh, cmd, timeout=30):
    print(f"  → {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    code = stdout.channel.recv_exit_status()
    if out.strip(): print(f"  ← {out.strip()[:500]}")
    if err.strip(): print(f"  ⚠ {err.strip()[:500]}")
    return code, out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.103.141.33", username="pepe", password="pepe1234")

# 1. Check GPU
print("=== GPU Status ===")
run(ssh, "nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader")

# 2. Check if backend container is running
print("\n=== Container Status ===")
run(ssh, "docker ps -a --filter name=documusic_backend --format '{{.Status}}'")

# 3. Check backend logs for OOM or crash
print("\n=== Backend Logs (last 80 lines) ===")
run(ssh, "docker logs documusic_backend --tail 80 2>&1", timeout=15)

# 4. Quick health check
print("\n=== Health Check ===")
code, out, err = run(ssh, "curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/", timeout=5)
print(f"  Backend HTTP: {out.strip()}")

ssh.close()
print("\n🏁 Check complete!")
