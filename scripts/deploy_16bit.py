"""Deploy 16-bit quantization fix to server: git pull + restart backend."""
import paramiko, time

def run(ssh, cmd, timeout=120):
    print(f"  → {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    code = stdout.channel.recv_exit_status()
    if out.strip(): print(f"  ← {out.strip()}")
    if err.strip(): print(f"  ⚠ {err.strip()}")
    return code, out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.103.141.33", username="pepe", password="pepe1234")

# 1. Git pull
code, out, err = run(ssh, "cd ~/documusic && git pull")
if "Already up to date" in out:
    print("✅ Already up to date")
elif code != 0:
    print(f"❌ Git pull failed: {err}")
    ssh.close()
    exit(1)

# 2. Restart backend container
code, out, err = run(ssh, "docker restart documusic_backend", timeout=30)
print(f"  Container restart: {'✅' if code == 0 else '❌'}")

# 3. Wait for backend to come online
print("⏳ Waiting for backend to come online...")
for i in range(30):
    time.sleep(3)
    code, out, err = run(ssh, "curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/", timeout=5)
    if "200" in out:
        print(f"✅ Backend ONLINE after {i*3}s")
        break
    print(f"  Attempt {i+1}/30 — waiting...")
else:
    print("❌ Backend did not come online after 90s")

# 4. Quick health check
run(ssh, "curl -s http://localhost:8000/ | python3 -m json.tool", timeout=10)

ssh.close()
print("🏁 Deploy complete!")
