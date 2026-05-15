"""Fix NCCL issue: uninstall conflicting nvidia-nccl-cu12."""
import paramiko

HOST = "100.103.141.33"
USER = "pepe"
PASS = "pepe1234"

def run(ssh, cmd, timeout=120):
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

# 1. Uninstall conflicting NCCL
run(ssh, "docker exec documusic_backend pip3 uninstall nvidia-nccl-cu12 -y 2>&1")

# 2. Verify torch works again
run(ssh, 'docker exec documusic_backend python3 -c "import torch; print(f\'torch: {torch.__version__}, CUDA: {torch.cuda.is_available()}\')" 2>&1')

# 3. Try importing ACE-Step pipeline
run(ssh, 'docker exec documusic_backend python3 -c "from acestep.pipeline_ace_step import ACEStepPipeline; print(\'✅ ACEStepPipeline importable\')" 2>&1')

# 4. Check the pipeline __init__ signature
run(ssh, 'docker exec documusic_backend python3 -c "from acestep.pipeline_ace_step import ACEStepPipeline; import inspect; sig = inspect.signature(ACEStepPipeline.__init__); print(sig)" 2>&1')

# 5. Check what methods the pipeline has
run(ssh, 'docker exec documusic_backend python3 -c "from acestep.pipeline_ace_step import ACEStepPipeline; print([m for m in dir(ACEStepPipeline) if not m.startswith(\'_\')])" 2>&1')

ssh.close()
print("\n✅ Done!")
