#!/usr/bin/env python3
"""Read infer.py from inside the Docker container."""
import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234', timeout=15)

# Read from inside container
cmds = [
    'docker exec documusic_backend sed -n "470,520p" /opt/YuE/inference/infer.py',
    'docker exec documusic_backend sed -n "420,470p" /opt/YuE/inference/infer.py',
    'docker exec documusic_backend find /app/outputs -type f 2>/dev/null | head -30',
]

for cmd in cmds:
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode()
    err = stderr.read().decode()
    print(out if out.strip() else "(empty)")
    if err.strip():
        print(f"[ERR] {err.strip()}")

ssh.close()
