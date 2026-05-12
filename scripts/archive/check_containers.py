#!/usr/bin/env python3
"""Check docker status on Madrid and find the correct container names"""
import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)
print("Conectado!")

cmds = [
    # All containers including stopped
    "docker ps -a",
    # Check if docker-compose exists in the project dir
    "ls -la /home/pepe/documusic/ 2>/dev/null || echo 'No /home/pepe/documusic'",
    "ls -la /opt/documusic/ 2>/dev/null || echo 'No /opt/documusic'",
    # Find docker-compose files
    "find / -name 'docker-compose.yml' -path '*/documusic/*' 2>/dev/null | head -5",
    # Check if there's a compose project
    "docker compose ls 2>/dev/null || docker-compose ls 2>/dev/null || echo 'No compose projects'",
]

for cmd in cmds:
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if out:
        print(f"  OUT: {out}")
    if err:
        print(f"  ERR: {err}")

ssh.close()
