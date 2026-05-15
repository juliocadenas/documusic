"""Check ACE-Step generation logs to see what prompt was sent."""
import paramiko

HOST = "100.103.141.33"
USER = "pepe"
PASS = "pepe1234"

def run(ssh, cmd, timeout=60):
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

# Check recent logs for ACE-Step generation
run(ssh, "docker logs documusic_backend --tail 50 2>&1")

ssh.close()
print("\nDone!")
