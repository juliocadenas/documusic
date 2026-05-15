"""Check job status and get detailed logs."""
import paramiko, json

def run(ssh, cmd, timeout=30):
    print(f"  → {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    code = stdout.channel.recv_exit_status()
    if out.strip(): print(f"  ← {out.strip()[:2000]}")
    if err.strip(): print(f"  ⚠ {err.strip()[:500]}")
    return code, out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.103.141.33", username="pepe", password="pepe1234")

# 1. Check job status
print("=== Job 44d655f7 Status ===")
run(ssh, "curl -s http://localhost:8000/api/job/44d655f7 | python3 -m json.tool")

# 2. Get full backend logs for this generation
print("\n=== Full Backend Logs (last 200 lines) ===")
run(ssh, "docker logs documusic_backend --tail 200 2>&1", timeout=20)

# 3. Check GPU memory details
print("\n=== GPU Memory ===")
run(ssh, "nvidia-smi")

# 4. Check outputs
print("\n=== Output Files ===")
run(ssh, "ls -la /home/pepe/documusic/backend/outputs/ 2>/dev/null || echo 'No outputs dir'")
run(ssh, "docker exec documusic_backend ls -la /app/outputs/ 2>/dev/null || echo 'No container outputs'")

ssh.close()
print("\n🏁 Done!")
