#!/usr/bin/env python3
"""Quick status check."""
import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234', timeout=15)

# Get last 50 lines looking for progress
stdin, stdout, stderr = ssh.exec_command('docker logs --tail 50 documusic_backend 2>&1 | grep -E "Stage|V1|%|error|Error|complete|saved|wav|soundfile"', timeout=15)
out = stdout.read().decode()
print("=== INFERENCE PROGRESS ===")
print(out if out.strip() else "No progress lines found")

# GPU
stdin, stdout, stderr = ssh.exec_command('nvidia-smi --query-gpu=power.draw,temperature.gpu,memory.used,utilization.gpu --format=csv,noheader', timeout=10)
print("=== GPU ===")
print(stdout.read().decode())

# Output files
stdin, stdout, stderr = ssh.exec_command('find /tmp -name "*.wav" -newer /tmp -mmin -15 2>/dev/null; ls -la /app/generated_songs/ 2>/dev/null || echo "no output dir"', timeout=10)
print("=== AUDIO FILES ===")
print(stdout.read().decode())

ssh.close()
