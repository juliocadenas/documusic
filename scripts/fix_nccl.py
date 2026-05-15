"""Fix NCCL issue and verify ACE-Step import."""
import paramiko

HOST = "100.103.141.33"
USER = "pepe"
PASS = "pepe1234"

def run(ssh, cmd, timeout=30):
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

# 1. Check if torch works at all in docker exec
run(ssh, 'docker exec documusic_backend python3 -c "import torch; print(torch.__version__); print(torch.cuda.is_available())" 2>&1')

# 2. Check NCCL version
run(ssh, 'docker exec documusic_backend python3 -c "import torch; print(torch.cuda.nccl.version())" 2>&1')

# 3. Check what nvidia-nccl packages are installed
run(ssh, "docker exec documusic_backend pip3 list 2>/dev/null | grep -i nccl")

# 4. Check LD_LIBRARY_PATH
run(ssh, "docker exec documusic_backend env | grep -i ld_")

# 5. Try with LD_LIBRARY_PATH set to CUDA libs
run(ssh, 'docker exec -e LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/local/lib/python3.10/dist-packages/torch/lib documusic_backend python3 -c "import torch; print(torch.__version__)" 2>&1')

# 6. Check if nvidia-nccl-cu12 was installed by diffusers
run(ssh, "docker exec documusic_backend pip3 show nvidia-nccl-cu12 2>/dev/null")

ssh.close()
print("\n✅ Done!")
