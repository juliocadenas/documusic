"""Fix torchvision: install nightly version matching PyTorch nightly cu128."""
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

# 1. Uninstall broken torchvision
run(ssh, "docker exec documusic_backend pip3 uninstall torchvision -y 2>&1 | tail -3")

# 2. Install torchvision from PyTorch nightly index (matching cu128)
print("\n⏳ Installing torchvision nightly for cu128...")
run(ssh, 
    "docker exec documusic_backend pip3 install --pre torchvision "
    "--index-url https://download.pytorch.org/whl/nightly/cu128 "
    "--no-deps --quiet 2>&1 | tail -5",
    timeout=600)

# 3. Verify torchvision works
run(ssh, 'docker exec documusic_backend python3 -c "import torchvision; print(f\'torchvision: {torchvision.__version__}\')" 2>&1')

# 4. Verify torch still works
run(ssh, 'docker exec documusic_backend python3 -c "import torch; print(f\'torch: {torch.__version__}, CUDA: {torch.cuda.is_available()}\')" 2>&1')

# 5. Try ACE-Step import
run(ssh, 'docker exec documusic_backend python3 -c "from acestep.pipeline_ace_step import ACEStepPipeline; print(\'✅ ACEStepPipeline importable\')" 2>&1')

# 6. Get pipeline __init__ signature
run(ssh, 'docker exec documusic_backend python3 -c "from acestep.pipeline_ace_step import ACEStepPipeline; import inspect; print(inspect.signature(ACEStepPipeline.__init__))" 2>&1')

# 7. Get pipeline __call__ signature  
run(ssh, 'docker exec documusic_backend python3 -c "from acestep.pipeline_ace_step import ACEStepPipeline; import inspect; print(inspect.signature(ACEStepPipeline.__call__))" 2>&1')

# 8. Read pipeline source directly (first 120 lines of __init__)
run(ssh, 'docker exec documusic_backend python3 -c "'
    'from acestep.pipeline_ace_step import ACEStepPipeline; '
    'import inspect; '
    'src = inspect.getsource(ACEStepPipeline.__init__); '
    'lines = src.split(chr(10)); '
    'print(chr(10).join(lines[:120]))'
    '" 2>&1')

# 9. Check backend still works
run(ssh, 'curl -s http://localhost:8000/ 2>&1')

ssh.close()
print("\n✅ Done!")
