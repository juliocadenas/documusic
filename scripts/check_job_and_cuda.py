"""Check the crashed job status and CUDA crash logs."""
import paramiko

def run(ssh, cmd, timeout=30):
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

# 1. Check the crashed job
print("=" * 60)
print("CRASHED JOB STATUS")
print("=" * 60)
run(ssh, "curl -s http://localhost:8000/api/job/1680259f | python3 -m json.tool")

# 2. Search for CUDA errors in full container logs
print("\n" + "=" * 60)
print("CUDA ERROR LOGS")
print("=" * 60)
run(ssh, "docker logs documusic_backend 2>&1 | grep -i 'cuda\\|error\\|crash\\|killed\\|oom\\|memory' | tail -40")

# 3. Check CUDA availability properly
print("\n" + "=" * 60)
print("CUDA INSIDE CONTAINER")
print("=" * 60)
run(ssh, '''docker exec documusic_backend python3 -c "import torch; print('CUDA:', torch.cuda.is_available()); print('Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A'); print('VRAM:', round(torch.cuda.get_device_properties(0).total_mem / 1024**3, 1), 'GB')"''')

# 4. Check ACE-Step model size
print("\n" + "=" * 60)
print("ACE-STEP MODEL SIZE")
print("=" * 60)
run(ssh, "du -sh /home/pepe/AI_MODELS/ace-step/models--ACE-Step--ACE-Step-v1-3.5B/ 2>/dev/null || echo 'Model path not found'")
run(ssh, "ls -la /home/pepe/AI_MODELS/ace-step/models--ACE-Step--ACE-Step-v1-3.5B/snapshots/*/  2>/dev/null | head -20")

ssh.close()
print("\nDone.")
