#!/usr/bin/env python3
"""Full status - unfiltered logs."""
import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234', timeout=15)

# Full last 30 lines
stdin, stdout, stderr = ssh.exec_command('docker logs --tail 30 documusic_backend 2>&1', timeout=15)
print("=== LAST 30 LOG LINES ===")
print(stdout.read().decode())

# GPU
stdin, stdout, stderr = ssh.exec_command('nvidia-smi', timeout=10)
print("=== GPU ===")
print(stdout.read().decode())

# Check tmp for any output
stdin, stdout, stderr = ssh.exec_command('find /tmp -name "*18ddfd2e*" -o -name "*.wav" 2>/dev/null | head -20', timeout=10)
print("=== TMP FILES ===")
print(stdout.read().decode())

# Check generated_songs inside container
stdin, stdout, stderr = ssh.exec_command('docker exec documusic_backend ls -la /app/generated_songs/ 2>/dev/null || echo "no songs dir"', timeout=10)
print("=== GENERATED SONGS (container) ===")
print(stdout.read().decode())

ssh.close()
