"""Install bitsandbytes in the container for 8-bit quantization."""
import paramiko
import time

def run(ssh, cmd, timeout=300):
    print(f"  → {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(f"  ← {out.strip()[-500:]}")
    if err.strip() and code != 0:
        print(f"  ⚠ {err.strip()[-500:]}")
    return out, err, code

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234')

print("=== Install bitsandbytes ===")

# 1) Check if bitsandbytes is installed
print("\n[1/3] Check bitsandbytes...")
out, _, _ = run(ssh, 'docker exec documusic_backend pip show bitsandbytes 2>&1 | head -5')

# 2) Install bitsandbytes
print("\n[2/3] Installing bitsandbytes...")
out, err, code = run(ssh, 'docker exec documusic_backend pip install -U bitsandbytes 2>&1', timeout=300)
print(f"  Exit code: {code}")

# 3) Verify
print("\n[3/3] Verify installation...")
run(ssh, 'docker exec documusic_backend python -c "import bitsandbytes; print(f\'bitsandbytes {bitsandbytes.__version__}\')" 2>&1')

# 4) Restart to be safe
print("\n[4/4] Restart backend...")
run(ssh, 'docker restart documusic_backend')
time.sleep(10)

# Health check
out, _, _ = run(ssh, 'curl -s http://localhost:8000/ | head -c 200')
print(f"\n✅ Health: {out.strip()[:150]}")

ssh.close()
print("\n✅ Done!")
