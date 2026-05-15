#!/usr/bin/env python3
"""Quick server check."""
import paramiko, sys
try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('100.103.141.33', username='pepe', password='pepe1234', timeout=10)
    print("✅ SERVER ALIVE")
    stdin, stdout, stderr = ssh.exec_command('uptime; nvidia-smi --query-gpu=power.draw,temp,memory.used --format=csv,noheader; docker logs --tail 5 documusic_backend 2>&1', timeout=10)
    print(stdout.read().decode())
    ssh.close()
except Exception as e:
    print(f"❌ SERVER DOWN: {e}")
