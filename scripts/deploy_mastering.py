"""Deploy mastering improvements + trigger test generation."""
import paramiko
import time
import json

def run(ssh, cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode().strip()

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.103.141.33", username="pepe", password="pepe1234")

# 1. Git pull
print("=== GIT PULL ===")
out = run(ssh, "cd ~/documusic && git pull")
print(out)

# 2. Restart backend
print("\n=== RESTART ===")
out = run(ssh, "docker restart documusic_backend")
print(f"Restart: {out}")

# 3. Wait for backend
print("\n=== WAITING ===")
for i in range(30):
    time.sleep(2)
    out = run(ssh, "curl -s http://localhost:8000/ | head -1", timeout=5)
    if '"status"' in out:
        print(f"Backend UP after {i*2}s")
        break
else:
    print("FAILED!")
    ssh.close()
    exit(1)

# 4. Trigger generation with longer lyrics
print("\n=== TRIGGER ===")
cmd = '''curl -s -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"style_prompt":"uplifting pop","lyrics":"[Verse]\\nShining bright like a diamond in the sky\\nFeeling alive I can touch the stars tonight\\nEvery moment feels like a dream come true\\nDancing in the moonlight just with you\\n[Chorus]\\nWe are the light we are the fire\\nBurning together reaching higher\\nNothing can stop us nothing can break\\nThis love we make is no mistake\\n[Verse]\\nRunning through the city lights so bright\\nHeartbeat racing feeling so right\\nEvery step we take is a brand new start\\nMusic playing straight from the heart"}' '''
out = run(ssh, cmd)
print(f"Response: {out}")
try:
    resp = json.loads(out)
    job_id = resp.get('job_id')
    print(f"\nJob ID: {job_id}")
except:
    print("Parse error")

ssh.close()
