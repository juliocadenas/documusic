#!/usr/bin/env python3
"""Verify the backend is running and the /api/outputs mount works"""
import paramiko
import time

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)
print("Conectado!")

def run_cmd(ssh, cmd, timeout=30):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if out:
        print(f"  OUT: {out}")
    if err:
        print(f"  ERR: {err}")
    return out, err

CONTAINER = "documusic_backend"

# Check container is running
run_cmd(ssh, f"docker ps --filter name={CONTAINER} --format '{{{{.Status}}}}'")

# Check the main.py inside container has the fix
run_cmd(ssh, f"docker exec {CONTAINER} grep 'app.mount' /app/main.py")

# Check backend health with python3 (not python)
run_cmd(ssh, f"docker exec {CONTAINER} python3 -c \"import urllib.request; r=urllib.request.urlopen('http://localhost:8000/'); print(r.read().decode()[:200])\"")

# Create a test MP3 file to verify the static mount works
run_cmd(ssh, f"docker exec {CONTAINER} bash -c 'echo test > /app/outputs/test.mp3'")

# Try to access it via the API path
run_cmd(ssh, f"docker exec {CONTAINER} python3 -c \"import urllib.request; r=urllib.request.urlopen('http://localhost:8000/api/outputs/test.mp3'); print('Status:', r.status, 'Content:', r.read()[:100])\"")

# Also check the host-side outputs directory
run_cmd(ssh, "ls -la /home/pepe/documusic/outputs/ | head -20")

# Check if the outputs volume is mounted
run_cmd(ssh, f"docker inspect {CONTAINER} --format '{{{{range .Mounts}}}}{{{{.Source}}}} -> {{{{.Destination}}}}\\n{{{{end}}}}'")

# Clean up test file
run_cmd(ssh, f"docker exec {CONTAINER} rm /app/outputs/test.mp3")

ssh.close()
print("\nVerificación completada!")
