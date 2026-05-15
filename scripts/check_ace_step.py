"""Check if ACE-Step is available on the server."""
import paramiko
import time

HOST = "100.103.141.33"
USER = "pepe"
PASS = "pepe1234"

def run(ssh, cmd, timeout=30):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(out[-2000:])
    if err: print(f"STDERR: {err[-1000:]}")
    return out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)
print(f"✅ Connected to {HOST}")

# 1. Check pip packages related to ace/step
run(ssh, "docker exec documusic_backend pip list 2>/dev/null | grep -iE 'ace|step'")

# 2. Check if ace_step module exists
run(ssh, "docker exec documusic_backend python -c 'import ace_step; print(ace_step.__file__)' 2>&1")

# 3. Check /opt directory
run(ssh, "docker exec documusic_backend ls /opt/ 2>/dev/null")

# 4. Search for any ace-step related files
run(ssh, "docker exec documusic_backend find /opt -maxdepth 3 -name '*ace*' -o -name '*ACE*' 2>/dev/null | head -20")

# 5. Check available disk space (need to download ~7GB model)
run(ssh, "df -h /home/pepe")

# 6. Check nvidia-smi for current state
run(ssh, "nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader")

# 7. Check if there's a HuggingFace cache with ACE-Step
run(ssh, "docker exec documusic_backend ls /root/.cache/huggingface/hub/ 2>/dev/null | head -20")

# 8. Check Python version
run(ssh, "docker exec documusic_backend python --version 2>&1")

# 9. Check torch version
run(ssh, "docker exec documusic_backend python -c 'import torch; print(torch.__version__)' 2>&1")

# 10. Check if diffusers is installed (ACE-Step may need it)
run(ssh, "docker exec documusic_backend pip list 2>/dev/null | grep -iE 'diffusers|transformers|accelerate'")

ssh.close()
print("\n✅ Done!")
