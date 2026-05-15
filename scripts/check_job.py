#!/usr/bin/env python3
"""Check job 21ae1802 status."""
import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234', timeout=15)

# Search for job in logs
stdin, stdout, stderr = ssh.exec_command('docker logs documusic_backend 2>&1 | grep -E "21ae1802|generate|Stage|Error|error|recons_mix|wav|mp3" | tail -40', timeout=30)
print("=== JOB LOGS ===")
print(stdout.read().decode())

# Check output files for this job
stdin, stdout, stderr = ssh.exec_command('docker exec documusic_backend find /app/outputs/21ae1802 -type f 2>/dev/null | head -20', timeout=15)
print("=== OUTPUT FILES ===")
out = stdout.read().decode()
print(out if out.strip() else "No output files found")

# Check generated_songs
stdin, stdout, stderr = ssh.exec_command('docker exec documusic_backend ls -la /app/generated_songs/ 2>/dev/null || echo "no songs dir"', timeout=15)
print("=== GENERATED SONGS ===")
print(stdout.read().decode())

# Check if server crashed (dmesg)
stdin, stdout, stderr = ssh.exec_command('sudo -S dmesg --time-format iso 2>/dev/null | grep -iE "pcie|aer|gpu|nvidia|error" | tail -10', timeout=15)
stdin.write("pepe1234\n")
stdin.flush()
print("=== DMESG ERRORS ===")
print(stdout.read().decode())

ssh.close()
