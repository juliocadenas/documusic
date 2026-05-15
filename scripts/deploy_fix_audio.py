"""Deploy _find_audio_file fix + trigger new generation."""
import paramiko
import time
import json

def run(ssh, cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.103.141.33", username="pepe", password="pepe1234")

# 1. Git pull
print("=== GIT PULL ===")
out, err = run(ssh, "cd ~/documusic && git pull")
print(out)
if err:
    print(f"ERR: {err}")

# 2. Restart backend
print("\n=== RESTART BACKEND ===")
out, err = run(ssh, "docker restart documusic_backend")
print(f"Restart: {out}")

# 3. Wait for backend to be ready
print("\n=== WAITING FOR BACKEND ===")
for i in range(30):
    time.sleep(2)
    out, _ = run(ssh, "curl -s http://localhost:8000/ | head -1", timeout=5)
    if '"status"' in out:
        print(f"Backend UP after {i*2}s")
        break
    print(f"  Waiting... ({i*2}s)")
else:
    print("Backend FAILED to start!")
    ssh.close()
    exit(1)

# 4. Trigger new generation
print("\n=== TRIGGER GENERATION ===")
gen_cmd = '''curl -s -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"style_prompt":"uplifting pop","lyrics":"[Verse]\\nShining bright like a diamond in the sky\\nFeeling alive I can touch the stars tonight\\n[Chorus]\\nWe are the light we are the fire\\nBurning together reaching higher"}' '''
out, _ = run(ssh, gen_cmd)
print(f"Response: {out}")

try:
    resp = json.loads(out)
    job_id = resp.get('job_id')
    print(f"\nJob ID: {job_id}")
    print(f"Monitor: python scripts/quick_check.py (update job_id to {job_id})")
except:
    print("Failed to parse response")

ssh.close()
