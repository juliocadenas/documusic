"""Deploy CUDA crash fix to server: git pull + restart backend."""
import paramiko
import time

def run(ssh, cmd, timeout=120):
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

# 1. Git pull
print("=" * 60)
print("GIT PULL")
print("=" * 60)
run(ssh, "cd ~/documusic && git pull")

# 2. Restart container
print("\n" + "=" * 60)
print("RESTART CONTAINER")
print("=" * 60)
run(ssh, "docker restart documusic_backend")

# 3. Wait for backend
print("\n" + "=" * 60)
print("WAITING FOR BACKEND...")
print("=" * 60)
for i in range(30):
    time.sleep(2)
    result = run(ssh, "curl -s http://localhost:8000/ | head -c 100", timeout=5)
    if '"status":"Online"' in result:
        print(f"\nBackend UP after {(i+1)*2}s!")
        break
    print(f"  Waiting... ({(i+1)*2}s)")

# 4. Verify
print("\n" + "=" * 60)
print("VERIFY")
print("=" * 60)
run(ssh, "curl -s http://localhost:8000/ | python3 -m json.tool | head -10")

ssh.close()
print("\nDone.")
