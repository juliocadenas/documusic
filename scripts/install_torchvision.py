"""Install torchvision + get ACEStepPipeline API signature."""
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

# 1. Install torchvision (matching PyTorch nightly cu128)
print("\n⏳ Installing torchvision for PyTorch nightly cu128...")
run(ssh, "docker exec documusic_backend pip3 install torchvision --no-deps --quiet 2>&1 | tail -5", timeout=300)

# 2. Verify torchvision
run(ssh, 'docker exec documusic_backend python3 -c "import torchvision; print(f\'torchvision: {torchvision.__version__}\')" 2>&1')

# 3. Try ACE-Step import again
run(ssh, 'docker exec documusic_backend python3 -c "from acestep.pipeline_ace_step import ACEStepPipeline; print(\'✅ ACEStepPipeline importable\')" 2>&1')

# 4. Get pipeline __init__ signature
run(ssh, 'docker exec documusic_backend python3 -c "from acestep.pipeline_ace_step import ACEStepPipeline; import inspect; print(inspect.signature(ACEStepPipeline.__init__))" 2>&1')

# 5. Get pipeline __call__ signature
run(ssh, 'docker exec documusic_backend python3 -c "from acestep.pipeline_ace_step import ACEStepPipeline; import inspect; print(inspect.signature(ACEStepPipeline.__call__))" 2>&1')

# 6. Get all public methods
run(ssh, 'docker exec documusic_backend python3 -c "from acestep.pipeline_ace_step import ACEStepPipeline; print([m for m in dir(ACEStepPipeline) if not m.startswith(\'_\')])" 2>&1')

# 7. Get __init__ source (first 80 lines)
run(ssh, 'docker exec documusic_backend python3 -c "from acestep.pipeline_ace_step import ACEStepPipeline; import inspect; src = inspect.getsource(ACEStepPipeline.__init__); lines = src.split(chr(10)); print(chr(10).join(lines[:80]))" 2>&1')

ssh.close()
print("\n✅ Done!")
