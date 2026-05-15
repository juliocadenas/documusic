"""Deploy 8-bit quantization fix to server: git pull + restart backend."""
import paramiko
import time

HOST = "100.103.141.33"
USER = "pepe"
PASS = "pepe1234"

def run(ssh, cmd, timeout=60):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip()[-2000:])
    if err.strip():
        print(f"STDERR: {err.strip()[-1000:]}")
    return out, err, code

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)
print(f"✅ Connected to {HOST}")

# 1. Git pull
run(ssh, "cd ~/documusic && git pull")

# 2. Restart backend container
run(ssh, "cd ~/documusic && docker compose restart documusic_backend", timeout=30)

# 3. Wait and check logs
print("\n⏳ Waiting 10s for container to start...")
time.sleep(10)

# 4. Check container is running
run(ssh, "docker ps --filter name=documusic_backend --format '{{.Status}}'")

# 5. Check startup logs for patching messages
out, err, code = run(ssh, "docker logs documusic_backend --tail 30 2>&1")
print("\n" + "="*60)
print("RECENT LOGS:")
print("="*60)
print(out[-3000:] if len(out) > 3000 else out)

# 6. Verify infer.py was patched correctly
out, err, code = run(ssh, "docker exec documusic_backend grep -A5 'AutoModelForCausalLM.from_pretrained' /opt/YuE/inference/infer.py 2>/dev/null | head -30")
print("\n" + "="*60)
print("INFER.PY from_pretrained CALLS:")
print("="*60)
print(out)

# 7. Check for model.to(device) commenting
out, err, code = run(ssh, "docker exec documusic_backend grep 'model.to\\|model = model.to\\|DocuMusic' /opt/YuE/inference/infer.py 2>/dev/null | head -10")
print("\n" + "="*60)
print("model.to() STATUS:")
print("="*60)
print(out)

ssh.close()
print("\n✅ Done!")
