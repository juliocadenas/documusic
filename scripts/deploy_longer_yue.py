"""Deploy longer YuE settings to server: git pull + restart backend."""
import paramiko
import time

def run(ssh, cmd, timeout=120):
    print(f"  → {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(f"  ← {out.strip()}")
    if err.strip() and code != 0:
        print(f"  ⚠ {err.strip()}")
    return out, err, code

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234')

print("=== Deploy YuE longer duration ===")

# 1) Git pull
print("\n[1/3] Git pull...")
run(ssh, 'cd ~/documusic && git pull origin main')

# 2) Check backend container status
print("\n[2/3] Check container...")
out, _, _ = run(ssh, 'docker ps --filter name=documusic_backend --format "{{.Status}}"')

# 3) Restart backend
print("\n[3/3] Restart backend...")
run(ssh, 'docker restart documusic_backend')

# Wait for backend to come up
print("\n⏳ Waiting 15s for backend startup...")
time.sleep(15)

# Check it's running
out, _, _ = run(ssh, 'docker ps --filter name=documusic_backend --format "{{.Status}}"')
print(f"\n✅ Container status: {out.strip()}")

# Quick health check
print("\n🏥 Health check...")
out, _, _ = run(ssh, 'curl -s http://localhost:8000/ | head -c 300')
print(f"  Response: {out.strip()[:200]}")

ssh.close()
print("\n✅ Deploy complete!")
