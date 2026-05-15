#!/usr/bin/env python3
"""Read patched infer.py around line 132."""
import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234', timeout=15)

stdin, stdout, stderr = ssh.exec_command('docker exec documusic_backend sed -n "120,145p" /opt/YuE/inference/infer.py', timeout=15)
print("=== infer.py lines 120-145 ===")
print(stdout.read().decode())

stdin, stdout, stderr = ssh.exec_command('docker exec documusic_backend sed -n "105,135p" /opt/YuE/inference/infer.py', timeout=15)
print("=== infer.py lines 105-135 ===")
print(stdout.read().decode())

ssh.close()
