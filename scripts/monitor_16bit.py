"""Monitor job 44d655f7 until completion."""
import paramiko, time, json

def run(ssh, cmd, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    return out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.103.141.33", username="pepe", password="pepe1234")

job_id = "44d655f7"
print(f"⏳ Monitoring job {job_id}...")

for i in range(60):  # Check every 15s for up to 15 minutes
    out, err = run(ssh, f"curl -s http://localhost:8000/api/job/{job_id}")
    try:
        job = json.loads(out)
        status = job.get("status", "unknown")
        logs = job.get("logs", [])
        completed = job.get("completed_variants", 0)
        total = job.get("num_variants", 1)
        audio_url = job.get("audio_url")

        # Show last 3 log lines
        last_logs = logs[-3:] if logs else []
        log_str = " | ".join(l[:80] for l in last_logs)

        print(f"[{i*15}s] Status: {status} | V{completed}/{total} | {log_str}")

        if status in ("done", "error", "failed"):
            print(f"\n🏁 Job finished: {status}")
            if audio_url:
                print(f"🎵 Audio: {audio_url}")
            if status in ("error", "failed"):
                print(f"❌ Error logs:")
                for l in logs[-10:]:
                    print(f"  {l}")
            break
    except json.JSONDecodeError:
        print(f"[{i*15}s] Could not parse response: {out[:100]}")

    time.sleep(15)

# Final GPU check
out, _ = run(ssh, "nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader")
print(f"\nGPU Memory: {out.strip()}")

ssh.close()
