"""Deploy optimization commit to server: git pull + restart backend."""
import paramiko
import time

def run(ssh, cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out.strip(): print(f"  ← {out.strip()[:500]}")
    if err.strip(): print(f"  ⚠ {err.strip()[:300]}")
    return out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.103.141.33", username="pepe", password="pepe1234")

# 1. Git pull
print("=== Git Pull ===")
run(ssh, "cd ~/documusic && git pull", timeout=30)

# 2. Restart backend
print("\n=== Restart Backend ===")
run(ssh, "cd ~/documusic && docker restart documusic_backend", timeout=30)

# 3. Wait for backend to be ready
print("\n=== Waiting for backend ===")
for i in range(30):
    time.sleep(2)
    out, _ = run(ssh, "curl -s http://localhost:8000/ | head -1", timeout=5)
    if "gpu" in out.lower() or "status" in out.lower() or "ok" in out.lower() or "yue" in out.lower():
        print(f"  ✅ Backend UP after {i*2}s")
        break
    print(f"  Waiting... ({i*2}s)")

# 4. Check GPU
print("\n=== GPU Status ===")
run(ssh, "nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader")

# 5. Verify yue_params
print("\n=== YUE_PARAMS ===")
run(ssh, "docker exec documusic_backend grep -A5 'YUE_PARAMS' /app/main.py | head -8")

ssh.close()
print("\n🏁 Deploy complete!")
