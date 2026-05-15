"""Fix PyTorch/torchaudio mismatch + install remaining ACE-Step deps."""
import paramiko

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

# 1. Uninstall current torch, torchvision, torchaudio
print("\n[1] Uninstalling current torch/torchvision/torchaudio...")
run(ssh, "docker exec documusic_backend pip3 uninstall torch torchvision torchaudio -y 2>&1 | tail -5")

# 2. Install PyTorch nightly + torchvision + torchaudio ALL from nightly index
print("\n[2] Installing PyTorch nightly + torchvision + torchaudio from nightly cu128...")
run(ssh,
    "docker exec documusic_backend pip3 install --pre torch torchvision torchaudio "
    "--index-url https://download.pytorch.org/whl/nightly/cu128 "
    "--quiet 2>&1 | tail -10",
    timeout=600)

# 3. Verify all three work together
print("\n[3] Verifying PyTorch stack...")
run(ssh, 'docker exec documusic_backend python3 -c "'
    'import torch; print(f\'torch: {torch.__version__}, CUDA: {torch.cuda.is_available()}\'); '
    'import torchvision; print(f\'torchvision: {torchvision.__version__}\'); '
    'import torchaudio; print(f\'torchaudio: {torchaudio.__version__}\'); '
    '" 2>&1')

# 4. Install remaining ACE-Step deps with --no-deps to prevent torch overwrite
print("\n[4] Installing remaining ACE-Step deps...")
# spacy is needed by acestep
run(ssh, "docker exec documusic_backend pip3 install spacy --quiet 2>&1 | tail -5", timeout=300)

# 5. Verify ACE-Step pipeline imports
print("\n[5] Testing ACE-Step import...")
run(ssh, 'docker exec documusic_backend python3 -c "from acestep.pipeline_ace_step import ACEStepPipeline; print(\'ACEStepPipeline importable\')" 2>&1')

# 6. Verify YuE backend still works
print("\n[6] Checking backend...")
run(ssh, 'curl -s http://localhost:8000/ 2>&1')

# 7. If backend is down, restart it
run(ssh, "docker restart documusic_backend 2>&1")
print("\nWaiting for backend restart...")
import time; time.sleep(10)
run(ssh, 'curl -s http://localhost:8000/ 2>&1')

ssh.close()
print("\nDone!")
