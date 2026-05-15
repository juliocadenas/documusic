"""Fix NCCL: install correct version and set LD_LIBRARY_PATH."""
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

# 1. Check what nvidia packages are installed
run(ssh, "docker exec documusic_backend pip3 list 2>/dev/null | grep -i nvidia")

# 2. Check torch version info
run(ssh, "docker exec documusic_backend cat /usr/local/lib/python3.10/dist-packages/torch/version.py 2>/dev/null | head -10")

# 3. Install nvidia-nccl-cu12 (needed by PyTorch nightly)
print("\n⏳ Installing nvidia-nccl-cu12...")
run(ssh, "docker exec documusic_backend pip3 install nvidia-nccl-cu12 2>&1 | tail -5", timeout=300)

# 4. Check where NCCL lib is
run(ssh, "docker exec documusic_backend find /usr/local/lib/python3.10/dist-packages/nvidia -name 'libnccl.so*' 2>/dev/null")

# 5. Try with LD_LIBRARY_PATH including NCCL
nccl_path = "/usr/local/lib/python3.10/dist-packages/nvidia/nccl/lib"
run(ssh, f'docker exec -e LD_LIBRARY_PATH="/usr/local/nvidia/lib:/usr/local/nvidia/lib64:{nccl_path}" documusic_backend python3 -c "import torch; print(f\'torch: {{torch.__version__}}, CUDA: {{torch.cuda.is_available()}}\')" 2>&1')

# 6. If that works, make it permanent by adding to the container environment
# For now, let's also try without LD_LIBRARY_PATH
run(ssh, 'docker exec documusic_backend python3 -c "import torch; print(torch.__version__)" 2>&1')

ssh.close()
print("\n✅ Done!")
