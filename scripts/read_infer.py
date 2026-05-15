#!/usr/bin/env python3
"""Read infer.py around line 500 to debug recons_mix error."""
import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234', timeout=15)

# Read lines 470-510 of infer.py
stdin, stdout, stderr = ssh.exec_command('sed -n "460,520p" /opt/YuE/inference/infer.py', timeout=15)
print("=== infer.py lines 460-520 ===")
print(stdout.read().decode())

# Also read lines 420-460 for context
stdin, stdout, stderr = ssh.exec_command('sed -n "420,460p" /opt/YuE/inference/infer.py', timeout=15)
print("=== infer.py lines 420-460 ===")
print(stdout.read().decode())

# Check what files were generated
stdin, stdout, stderr = ssh.exec_command('find /app/outputs/18ddfd2e -type f 2>/dev/null | head -30', timeout=15)
print("=== OUTPUT FILES ===")
print(stdout.read().decode())

ssh.close()
