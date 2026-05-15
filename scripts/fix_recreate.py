"""Emergency fix: recreate container + install ACE deps without breaking PyTorch."""
import paramiko
import time

HOST = "100.103.141.33"
USER = "pepe"
PASS = "pepe1234"

def run(ssh, cmd, timeout=300):
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
print(f"✅ Connected to {HOST}")

# 1. Recreate container from scratch (restores original Docker image)
print("\n🔄 Recreating container...")
run(ssh, "cd ~/documusic && docker compose up -d --force-recreate documusic_backend", timeout=120)

# 2. Wait for startup
print("\n⏳ Waiting 20s for container startup...")
time.sleep(20)

# 3. Verify backend is up and YuE works
run(ssh, "docker logs documusic_backend --tail 5 2>&1")
run(ssh, "curl -s http://localhost:8000/ 2>&1 | head -1")

# 4. Verify torch works
run(ssh, 'docker exec documusic_backend python3 -c "import torch; print(f\'torch: {torch.__version__}, CUDA: {torch.cuda.is_available()}\')" 2>&1')

# 5. Install ACE-Step deps CAREFULLY (no-deps for packages that might pull nvidia-nccl)
safe_deps = [
    "librosa==0.11.0",
    "loguru==0.7.3",
    "pypinyin==0.53.0",
    "py3langid==0.3.0",
    "num2words==0.5.14",
    "cutlet",
    "fugashi[unidic-lite]",
    "hangul-romanize==0.1.0",
]

for dep in safe_deps:
    run(ssh, f"docker exec documusic_backend pip3 install '{dep}' --quiet 2>&1 | tail -2", timeout=180)

# 6. Install diffusers with --no-deps to prevent nvidia-nccl-cu12
print("\n⚠️ Installing diffusers with --no-deps to prevent NCCL conflict...")
run(ssh, "docker exec documusic_backend pip3 install diffusers --no-deps --quiet 2>&1 | tail -3", timeout=120)

# 7. Install acestep package with --no-deps
run(ssh, "docker exec documusic_backend pip3 install --no-deps -e /opt/ACE-Step 2>&1 | tail -3", timeout=60)

# 8. Verify torch still works after installs
run(ssh, 'docker exec documusic_backend python3 -c "import torch; print(f\'torch: {torch.__version__}, CUDA: {torch.cuda.is_available()}\')" 2>&1')

# 9. Verify ACE-Step pipeline is importable
run(ssh, 'docker exec documusic_backend python3 -c "from acestep.pipeline_ace_step import ACEStepPipeline; print(\'✅ ACEStepPipeline importable\')" 2>&1')

# 10. Get pipeline signature
run(ssh, 'docker exec documusic_backend python3 -c "from acestep.pipeline_ace_step import ACEStepPipeline; import inspect; print(inspect.signature(ACEStepPipeline.__init__))" 2>&1')

# 11. Get pipeline methods
run(ssh, 'docker exec documusic_backend python3 -c "from acestep.pipeline_ace_step import ACEStepPipeline; print([m for m in dir(ACEStepPipeline) if not m.startswith(\'_\')])" 2>&1')

ssh.close()
print("\n✅ Emergency fix complete!")
