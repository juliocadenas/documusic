"""Debug why vocals are not appearing — check vtrack/itrack, prompt format, and model output."""
import paramiko, json

def run(ssh, cmd, timeout=30):
    print(f"  → {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip(): print(f"  ← {out.strip()[:2000]}")
    if err.strip(): print(f"  ⚠ {err.strip()[:500]}")
    return out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.103.141.33", username="pepe", password="pepe1234")

job_id = "44d655f7"

# 1. Check output directory for this job
print(f"=== Output files for {job_id} ===")
run(ssh, f"docker exec documusic_backend ls -la /app/outputs/{job_id}/")

# 2. Check if vtrack and itrack exist
print(f"\n=== Vocal/Instrumental tracks ===")
run(ssh, f"docker exec documusic_backend find /app/outputs/{job_id}/ -name '*.wav' -o -name '*.npy' | head -20")

# 3. Check the prompt files that were used
print(f"\n=== Style prompt (genre_txt) ===")
run(ssh, f"docker exec documusic_backend find /tmp/ -name 'style.txt' -newer /app/outputs/{job_id}/ 2>/dev/null | head -5")
run(ssh, f"docker exec documusic_backend find /tmp/ -name 'lyrics.txt' -newer /app/outputs/{job_id}/ 2>/dev/null | head -5")

# 4. Check the actual job data for prompt info
print(f"\n=== Job details ===")
out, _ = run(ssh, f"curl -s http://localhost:8000/api/job/{job_id}")
try:
    job = json.loads(out)
    print(f"  Status: {job.get('status')}")
    print(f"  Audio URL: {job.get('audio_url')}")
    print(f"  Variants: {len(job.get('variants', []))}")
    for v in job.get('variants', []):
        print(f"    Variant {v.get('index')}: duration={v.get('duration')}s, url={v.get('audio_url')}, error={v.get('error')}")
    print(f"  Logs (last 20):")
    for l in job.get('logs', [])[-20:]:
        print(f"    {l}")
except:
    pass

# 5. Check if the model is actually generating vocal tokens
# Look at the numpy files sizes
print(f"\n=== Numpy file sizes (vocal vs instrumental tokens) ===")
run(ssh, f"docker exec documusic_backend find /app/outputs/{job_id}/ -name '*.npy' -exec ls -la {{}} \\;")

# 6. Check wav file sizes
print(f"\n=== WAV file sizes ===")
run(ssh, f"docker exec documusic_backend find /app/outputs/{job_id}/ -name '*.wav' -exec ls -la {{}} \\;")

# 7. Check the mp3 file
print(f"\n=== MP3 file ===")
run(ssh, f"docker exec documusic_backend ls -la /app/outputs/{job_id}.mp3 2>/dev/null")

# 8. Check the infer.py code for how it handles vocal generation
print(f"\n=== YuE infer.py vocal handling ===")
run(ssh, "grep -n 'vtrack\\|itrack\\|rearrange\\|codec_ids\\|vocal' /opt/YuE/inference/infer.py | head -30")

# 9. Check what the actual genre prompt looks like after enrichment
print(f"\n=== Last generation's style prompt ===")
# Check the backend logs for the style prompt
run(ssh, f"docker logs documusic_backend 2>&1 | grep -i 'style\\|genre\\|enrich\\|prompt' | tail -20")

ssh.close()
print("\n🏁 Debug complete!")
