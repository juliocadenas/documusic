"""Read ACE-Step __call__ return value and save logic."""
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

# Read the end of __call__ to see return value
run(ssh, "docker exec documusic_backend sed -n '1700,1850p' /opt/ACE-Step/acestep/pipeline_ace_step.py 2>&1")

# Also read the infer-api.py for usage example
run(ssh, "docker exec documusic_backend cat /opt/ACE-Step/infer-api.py 2>&1")

ssh.close()
print("\nDone!")
