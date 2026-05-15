"""Verify infer.py patching on server."""
import paramiko

HOST = "100.103.141.33"
USER = "pepe"
PASS = "pepe1234"

def run(ssh, cmd, timeout=30):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip():
        print(out.strip()[-3000:])
    if err.strip():
        print(f"STDERR: {err.strip()[-1000:]}")
    return out

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)
print(f"✅ Connected to {HOST}")

# Check from_pretrained calls
print("\n" + "="*60)
print("from_pretrained CALLS:")
print("="*60)
run(ssh, "docker exec documusic_backend grep -n -B2 -A6 'from_pretrained' /opt/YuE/inference/infer.py 2>/dev/null")

# Check for any syntax errors by trying to compile
print("\n" + "="*60)
print("SYNTAX CHECK:")
print("="*60)
run(ssh, "docker exec documusic_backend python3 -c \"import py_compile; py_compile.compile('/opt/YuE/inference/infer.py', doraise=True)\" 2>&1")

# Check markers
print("\n" + "="*60)
print("PATCH MARKERS:")
print("="*60)
run(ssh, "docker exec documusic_backend grep -n 'load_in_8bit\\|mp3_to_wav\\|torchaudio_patched\\|DocuMusic' /opt/YuE/inference/infer.py 2>/dev/null")

# Check startup logs
print("\n" + "="*60)
print("STARTUP LOGS (last 40 lines):")
print("="*60)
run(ssh, "docker logs documusic_backend --tail 40 2>&1")

ssh.close()
print("\n✅ Verification complete!")
