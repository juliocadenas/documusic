"""Read ACE-Step __call__ method and check install status."""
import paramiko

HOST = "100.103.141.33"
USER = "pepe"
PASS = "pepe1234"

def run(ssh, cmd, timeout=60):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip(): print(out.strip()[-4000:])
    if err.strip(): print(f"STDERR: {err.strip()[-2000:]}")
    return out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)

# Read __call__ method (lines 1445-1530)
run(ssh, "docker exec documusic_backend sed -n '1445,1540p' /opt/ACE-Step/acestep/pipeline_ace_step.py 2>&1")

# Check what model dirs exist in ACE-Step model dir
run(ssh, "docker exec documusic_backend ls -la /app/models/ACE-Step-v1.5/ 2>&1")
run(ssh, "docker exec documusic_backend ls -la /opt/ACE-Step/ 2>&1 | head -20")

# Check if install_ace_all_deps finished (check if spacy is installed)
run(ssh, 'docker exec documusic_backend python3 -c "import spacy; print(f\'spacy: {spacy.__version__}\')" 2>&1')

# Check torch still works
run(ssh, 'docker exec documusic_backend python3 -c "import torch; print(f\'torch: {torch.__version__}, CUDA: {torch.cuda.is_available()}\')" 2>&1')

ssh.close()
print("\nDone!")
