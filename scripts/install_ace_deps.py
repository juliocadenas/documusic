"""Install ACE-Step dependencies manually on the server."""
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
    code = stdout.channel.recv_exit_status()
    if out.strip(): print(out.strip()[-2000:])
    if err.strip(): print(f"STDERR: {err.strip()[-1500:]}")
    return out, err, code

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)
print(f"✅ Connected to {HOST}")

# Install critical ACE-Step dependencies (inference only, skip training deps)
deps = [
    "diffusers>=0.33.0",
    "librosa==0.11.0",
    "loguru==0.7.3",
    "pypinyin==0.53.0",
    "py3langid==0.3.0",
    "num2words==0.5.14",
    "cutlet",
    "fugashi[unidic-lite]",
    "hangul-romanize==0.1.0",
]

for dep in deps:
    print(f"\n{'='*40}")
    print(f"Installing {dep}...")
    run(ssh, f"docker exec documusic_backend pip3 install '{dep}' --quiet 2>&1 | tail -3", timeout=180)

# Also install acestep package itself (from the cloned repo)
print(f"\n{'='*40}")
print("Installing acestep package (no-deps, since we installed deps manually)...")
run(ssh, "docker exec documusic_backend pip3 install --no-deps -e /opt/ACE-Step 2>&1 | tail -5", timeout=60)

# Verify import
print(f"\n{'='*40}")
print("Verifying import...")
run(ssh, 'docker exec documusic_backend python3 -c "from acestep.pipeline_ace_step import ACEStepPipeline; print(\'✅ ACEStepPipeline importable\')" 2>&1')

# Check what the pipeline class looks like
run(ssh, 'docker exec documusic_backend python3 -c "from acestep.pipeline_ace_step import ACEStepPipeline; import inspect; print(inspect.signature(ACEStepPipeline.__init__))" 2>&1')

ssh.close()
print("\n✅ Dependencies installed!")
