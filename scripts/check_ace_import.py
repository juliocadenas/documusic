"""Check if ACE-Step is importable and inspect its API."""
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

# 1. Check if acestep is importable
run(ssh, 'docker exec documusic_backend python3 -c "import acestep; print(dir(acestep))" 2>&1')

# 2. Check acestep module structure
run(ssh, "docker exec documusic_backend ls -la /opt/ACE-Step/acestep/ 2>/dev/null")

# 3. Check if pipeline module exists
run(ssh, "docker exec documusic_backend find /opt/ACE-Step/acestep -name '*.py' -type f 2>/dev/null")

# 4. Try importing the pipeline
run(ssh, 'docker exec documusic_backend python3 -c "from acestep.pipeline import ACEStepPipeline; print(\'Pipeline OK\')" 2>&1')

# 5. Check ACE-Step requirements
run(ssh, "docker exec documusic_backend cat /opt/ACE-Step/requirements.txt 2>/dev/null")

# 6. Check what pip packages are missing
run(ssh, "docker exec documusic_backend pip3 list 2>/dev/null | grep -iE 'diffusers|ace|probables|flash-attn'")

# 7. Check setup.py for dependencies
run(ssh, "docker exec documusic_backend cat /opt/ACE-Step/setup.py 2>/dev/null")

ssh.close()
print("\n✅ Done!")
