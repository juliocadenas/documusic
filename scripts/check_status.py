"""Check server status: GPU, backend, container."""
import paramiko

def run(ssh, cmd, timeout=30):
    print(f"\n>>> {cmd}")
    try:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode('utf-8', errors='replace').strip()
        err = stderr.read().decode('utf-8', errors='replace').strip()
        if out:
            print(out)
        if err:
            print(f"[STDERR] {err}")
        return out
    except Exception as e:
        print(f"[ERROR] {e}")
        return ""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234')

# 1. Check GPU
print("=" * 60)
print("GPU STATUS")
print("=" * 60)
run(ssh, "nvidia-smi")

# 2. Check container
print("\n" + "=" * 60)
print("CONTAINER STATUS")
print("=" * 60)
run(ssh, "docker ps -a --filter name=documusic")

# 3. Check backend health
print("\n" + "=" * 60)
print("BACKEND HEALTH")
print("=" * 60)
run(ssh, "curl -s http://localhost:8000/ || echo 'BACKEND DOWN'")

# 4. Recent logs
print("\n" + "=" * 60)
print("RECENT LOGS (last 50 lines)")
print("=" * 60)
run(ssh, "docker logs --tail 50 documusic_backend 2>&1")

# 5. Check CUDA availability inside container
print("\n" + "=" * 60)
print("CUDA CHECK INSIDE CONTAINER")
print("=" * 60)
run(ssh, 'docker exec documusic_backend python3 -c "import torch; print(f\'CUDA available: {torch.cuda.is_available()}\'); print(f\'Device count: {torch.cuda.device_count()}\'); print(f\'Device name: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \'N/A\'}\')"')

ssh.close()
print("\nDone.")
