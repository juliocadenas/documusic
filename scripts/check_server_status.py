"""Check if server is alive and diagnose."""
import paramiko
import time

HOST = "100.103.141.33"
USER = "pepe"
PASS = "pepe1234"

def run(ssh, cmd, timeout=30):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip():
        print(out.strip()[-2000:])
    if err.strip():
        print(f"STDERR: {err.strip()[-1000:]}")
    return out, err

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)
    print(f"✅ Server {HOST} is UP")

    # Check uptime
    run(ssh, "uptime")

    # Check docker
    run(ssh, "docker ps -a --filter name=documusic --format '{{.Names}} {{.Status}}'")

    # Check dmesg for PCIe errors
    out, _ = run(ssh, "sudo dmesg | grep -i 'aer\\|pcie\\|error\\|fatal' | tail -20")

    # Check backend logs
    run(ssh, "docker logs documusic_backend --tail 50 2>&1")

    # Check GPU
    run(ssh, "nvidia-smi --query-gpu=name,memory.used,memory.total,power.draw --format=csv,noheader 2>&1")

    ssh.close()
except Exception as e:
    print(f"❌ Cannot connect to server: {e}")
