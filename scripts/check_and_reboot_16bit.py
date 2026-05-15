"""Wait for server to come back, check status, reboot if needed."""
import paramiko, time

def try_connect(timeout=10):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect("100.103.141.33", username="pepe", password="pepe1234", timeout=timeout)
        return ssh
    except Exception as e:
        print(f"  Connection failed: {e}")
        return None

def run(ssh, cmd, timeout=30):
    print(f"  → {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    code = stdout.channel.recv_exit_status()
    if out.strip(): print(f"  ← {out.strip()[:800]}")
    if err.strip(): print(f"  ⚠ {err.strip()[:300]}")
    return code, out, err

# Try connecting for 2 minutes
print("⏳ Waiting for server to respond (up to 3 minutes)...")
ssh = None
for i in range(18):  # 18 * 10s = 3 minutes
    ssh = try_connect(timeout=10)
    if ssh:
        print(f"✅ Connected after {i*10}s")
        break
    print(f"  Attempt {i+1}/18 — retrying in 10s...")
    time.sleep(10)

if not ssh:
    print("❌ Server unreachable after 3 minutes. Forcing reboot...")
    # Try force reboot
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect("100.103.141.33", username="pepe", password="pepe1234", timeout=15)
        run(ssh, "echo pepe1234 | sudo -S reboot now", timeout=10)
        ssh.close()
    except:
        print("  Cannot reach server for reboot either. Manual intervention needed.")
    exit(1)

# Connected — check status
print("\n=== GPU Status ===")
run(ssh, "nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader")

print("\n=== Container Status ===")
run(ssh, "docker ps -a --filter name=documusic_backend --format '{{.Status}}'")

print("\n=== Backend Logs (last 100 lines) ===")
run(ssh, "docker logs documusic_backend --tail 100 2>&1", timeout=15)

print("\n=== Health Check ===")
code, out, err = run(ssh, "curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/", timeout=5)
print(f"  Backend HTTP: {out.strip()}")

if "200" not in out:
    print("\n🔄 Backend not responding, restarting...")
    run(ssh, "docker restart documusic_backend", timeout=30)
    time.sleep(5)
    for i in range(15):
        time.sleep(3)
        code, out, err = run(ssh, "curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/", timeout=5)
        if "200" in out:
            print(f"✅ Backend ONLINE after {i*3}s")
            break

ssh.close()
print("\n🏁 Check complete!")
