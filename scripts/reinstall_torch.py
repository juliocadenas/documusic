"""Reinstall PyTorch nightly to fix NCCL issue."""
import paramiko
import time

HOST = "100.103.141.33"
USER = "pepe"
PASS = "pepe1234"

def run(ssh, cmd, timeout=600):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip(): print(out.strip()[-2000:])
    if err.strip(): print(f"STDERR: {err.strip()[-1500:]}")
    return out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)

# 1. Find system NCCL libraries
run(ssh, "docker exec documusic_backend find / -name 'libnccl.so*' 2>/dev/null | head -10")

# 2. Check if CUDA toolkit has NCCL
run(ssh, "docker exec documusic_backend ls /usr/local/cuda/lib64/libnccl* 2>/dev/null")

# 3. Reinstall PyTorch nightly (force-reinstall, no-deps for speed)
print("\n⏳ Reinstalando PyTorch nightly (esto puede tardar 2-3 min)...")
run(ssh, "docker exec documusic_backend pip3 install --pre torch torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128 --force-reinstall --no-deps 2>&1 | tail -10", timeout=600)

# 4. Verify torch works
run(ssh, 'docker exec documusic_backend python3 -c "import torch; print(f\'torch: {torch.__version__}, CUDA: {torch.cuda.is_available()}\')" 2>&1')

# 5. Try importing ACE-Step pipeline
run(ssh, 'docker exec documusic_backend python3 -c "from acestep.pipeline_ace_step import ACEStepPipeline; print(\'✅ ACEStepPipeline importable\')" 2>&1')

# 6. Get pipeline signature
run(ssh, 'docker exec documusic_backend python3 -c "from acestep.pipeline_ace_step import ACEStepPipeline; import inspect; print(inspect.signature(ACEStepPipeline.__init__))" 2>&1')

# 7. Restart backend to pick up the fix
run(ssh, "cd ~/documusic && docker compose restart documusic_backend", timeout=60)

# 8. Wait and verify
print("\n⏳ Waiting 15s for restart...")
time.sleep(15)
run(ssh, "docker logs documusic_backend --tail 10 2>&1")
run(ssh, 'curl -s http://localhost:8000/ 2>&1 | python3 -c "import sys,json; d=json.load(sys.stdin); print(\'models_available:\', d.get(\'models_available\'))"')

ssh.close()
print("\n✅ Done!")
