"""Install torchcodec to fix torchaudio.save() error."""
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

# Install torchcodec with --no-deps to prevent torch overwrite
run(ssh, "docker exec documusic_backend pip3 install torchcodec --no-deps --quiet 2>&1 | tail -5", timeout=300)

# Verify
run(ssh, 'docker exec documusic_backend python3 -c "import torchcodec; print(f\'torchcodec: {torchcodec.__version__}\')" 2>&1')

# Quick test: torchaudio.save should work now
run(ssh, 'docker exec documusic_backend python3 -c "'
    'import torch; import torchaudio; '
    't = torch.zeros(1, 44100); '
    'torchaudio.save("/tmp/test_tc.wav", t, 44100); '
    'import os; print(f\'test wav: {os.path.getsize("/tmp/test_tc.wav")} bytes\'); '
    'os.remove("/tmp/test_tc.wav"); '
    '" 2>&1')

ssh.close()
print("\nDone!")
