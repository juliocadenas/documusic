#!/usr/bin/env python3
"""Check detailed backend logs."""
import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234', timeout=10)

# Last 40 lines of logs
stdin, stdout, stderr = ssh.exec_command('docker logs --tail 40 documusic_backend 2>&1', timeout=15)
print(stdout.read().decode())

# GPU status
stdin, stdout, stderr = ssh.exec_command('nvidia-smi', timeout=10)
print(stdout.read().decode())

# Check output files
stdin, stdout, stderr = ssh.exec_command('ls -la /tmp/yue_* 2>/dev/null; ls -la ~/documusic/backend/generated_songs/ 2>/dev/null', timeout=10)
print("=== OUTPUT FILES ===")
print(stdout.read().decode())

ssh.close()
