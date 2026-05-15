"""Read ACE-Step requirements and install all missing deps at once."""
import paramiko
import re

HOST = "100.103.141.33"
USER = "pepe"
PASS = "pepe1234"

def run(ssh, cmd, timeout=300):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip(): print(out.strip()[-3000:])
    if err.strip(): print(f"STDERR: {err.strip()[-2000:]}")
    return out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)

# 1. Read ACE-Step setup.py / pyproject.toml / requirements.txt
print("\n[INFO] Checking ACE-Step dependency files...")
run(ssh, "docker exec documusic_backend ls /opt/ACE-Step/*.txt /opt/ACE-Step/*.toml /opt/ACE-Step/setup.py /opt/ACE-Step/setup.cfg 2>&1")

# 2. Read requirements if exists
run(ssh, "docker exec documusic_backend cat /opt/ACE-Step/requirements.txt 2>&1")

# 3. Read setup.py dependencies
run(ssh, "docker exec documusic_backend cat /opt/ACE-Step/setup.py 2>&1")

# 4. Read pyproject.toml if exists
run(ssh, "docker exec documusic_backend cat /opt/ACE-Step/pyproject.toml 2>&1")

# 5. Now install all ACE-Step deps properly
# Strategy: install acestep with deps but exclude nvidia-nccl-cu12
print("\n[INFO] Installing ACE-Step with all deps (excluding nvidia-nccl-cu12)...")

# First, pin nvidia-nccl-cu12 to a dummy version to prevent install
run(ssh, 'docker exec documusic_backend bash -c "echo \'nvidia-nccl-cu12==999.99.99\' > /tmp/constraints.txt"')

# Install acestep with constraint to block nvidia-nccl-cu12
run(ssh, 
    "docker exec documusic_backend pip3 install -e /opt/ACE-Step "
    "--constraint /tmp/constraints.txt "
    "--quiet 2>&1 | tail -20",
    timeout=600)

# 6. Verify torch still works
run(ssh, 'docker exec documusic_backend python3 -c "import torch; print(f\'torch: {torch.__version__}, CUDA: {torch.cuda.is_available()}\')" 2>&1')

# 7. Try ACE-Step import
run(ssh, 'docker exec documusic_backend python3 -c "from acestep.pipeline_ace_step import ACEStepPipeline; print(\'✅ ACEStepPipeline importable\')" 2>&1')

# 8. Get pipeline __init__ signature
run(ssh, 'docker exec documusic_backend python3 -c "from acestep.pipeline_ace_step import ACEStepPipeline; import inspect; print(inspect.signature(ACEStepPipeline.__init__))" 2>&1')

# 9. Get pipeline __call__ signature  
run(ssh, 'docker exec documusic_backend python3 -c "from acestep.pipeline_ace_step import ACEStepPipeline; import inspect; print(inspect.signature(ACEStepPipeline.__call__))" 2>&1')

# 10. Read __init__ source
run(ssh, 'docker exec documusic_backend python3 -c "'
    'from acestep.pipeline_ace_step import ACEStepPipeline; '
    'import inspect; '
    'src = inspect.getsource(ACEStepPipeline.__init__); '
    'lines = src.split(chr(10)); '
    'print(chr(10).join(lines[:100]))'
    '" 2>&1')

# 11. Check backend still works
run(ssh, 'curl -s http://localhost:8000/ 2>&1')

ssh.close()
print("\n✅ Done!")
