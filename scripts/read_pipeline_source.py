"""Read ACE-Step pipeline source code from server."""
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

# Read the pipeline file directly
run(ssh, "docker exec documusic_backend head -200 /opt/ACE-Step/acestep/pipeline_ace_step.py 2>&1")

# Read the ACEStepPipeline class __init__ method
run(ssh, "docker exec documusic_backend grep -n 'class ACEStepPipeline\\|def __init__\\|def __call__\\|checkpoint_dir\\|def __forward' /opt/ACE-Step/acestep/pipeline_ace_step.py 2>&1")

# Read lines around __init__
run(ssh, "docker exec documusic_backend sed -n '60,180p' /opt/ACE-Step/acestep/pipeline_ace_step.py 2>&1")

ssh.close()
print("\nDone!")
