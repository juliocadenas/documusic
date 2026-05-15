"""Verify backend + upgrade transformers for ACE-Step."""
import paramiko

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

# 1. Check backend is up
run(ssh, "curl -s http://localhost:8000/ 2>&1 | head -1")

# 2. Check startup logs
run(ssh, "docker logs documusic_backend --tail 15 2>&1")

# 3. Upgrade transformers to 4.50.0 (needed by ACE-Step)
print("\n⏳ Upgrading transformers to 4.50.0...")
run(ssh, "docker exec documusic_backend pip3 install transformers==4.50.0 --quiet 2>&1 | tail -3", timeout=300)

# 4. Verify torch still works
run(ssh, 'docker exec documusic_backend python3 -c "import torch; print(f\'torch: {torch.__version__}, CUDA: {torch.cuda.is_available()}\')" 2>&1')

# 5. Verify ACE-Step pipeline importable
run(ssh, 'docker exec documusic_backend python3 -c "from acestep.pipeline_ace_step import ACEStepPipeline; print(\'✅ ACEStepPipeline importable\')" 2>&1')

# 6. Get pipeline __init__ signature
run(ssh, 'docker exec documusic_backend python3 -c "from acestep.pipeline_ace_step import ACEStepPipeline; import inspect; print(inspect.signature(ACEStepPipeline.__init__))" 2>&1')

# 7. Get pipeline methods
run(ssh, 'docker exec documusic_backend python3 -c "from acestep.pipeline_ace_step import ACEStepPipeline; print([m for m in dir(ACEStepPipeline) if not m.startswith(\'_\')])" 2>&1')

# 8. Check backend API
run(ssh, 'curl -s http://localhost:8000/ 2>&1')

ssh.close()
print("\n✅ Done!")
