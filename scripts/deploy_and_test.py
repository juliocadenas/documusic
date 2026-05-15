"""Deploy updated params and trigger generation via API."""
import paramiko
import time
import json

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

# 1. Git pull + restart
print("=== Deploy ===")
run(ssh, "cd ~/documusic && git pull", timeout=30)
run(ssh, "cd ~/documusic && docker restart documusic_backend", timeout=30)

# 2. Wait for backend
print("\n=== Waiting for backend ===")
for i in range(30):
    time.sleep(2)
    out, _ = run(ssh, "curl -s http://localhost:8000/ | head -1", timeout=5)
    if "status" in out.lower() or "online" in out.lower():
        print(f"  ✅ Backend UP after {i*2}s")
        break

# 3. Verify params
print("\n=== YUE_PARAMS ===")
run(ssh, "docker exec documusic_backend grep -A5 'YUE_PARAMS' /app/main.py | head -8")

# 4. Trigger generation via API
print("\n=== Triggering Generation ===")
gen_cmd = """curl -s -X POST http://localhost:8000/api/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "style_prompt": "uplifting female pop",
    "lyrics": "[verse]\\nIn the silence of the night, stars are shining bright\\nEvery dream I hold inside, feels like taking flight\\nThrough the darkness theres a spark, guiding me so far\\nI believe in who I am, Im a shooting star\\n\\n[chorus]\\nRise above the clouds, let the music play\\nNothings gonna stop us on this beautiful day\\nFeel the rhythm in your heart, let it show you the way\\nWere unstoppable together, come what may\\n\\n[verse]\\nEvery step I take ahead, echoes in my mind\\nLeaving all the doubts behind, treasures I will find\\nWith the wind beneath my wings, soaring ever high\\nReaching for the rainbow, painting up the sky",
    "num_variants": 1,
    "quantization": "16bit"
  }'"""

out, _ = run(ssh, gen_cmd, timeout=30)
print(f"  Response: {out[:500]}")

# Parse job_id
try:
    data = json.loads(out)
    job_id = data.get("job_id", "unknown")
    print(f"\n  🎵 Job ID: {job_id}")
    print(f"  Monitor: curl http://localhost:8000/api/job/{job_id}")
except:
    print("  Could not parse response")

# 5. Check GPU
print("\n=== GPU ===")
run(ssh, "nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader")

ssh.close()
print("\n🏁 Generation triggered! Monitor with: python scripts/check_job_live.py")
