#!/usr/bin/env python3
"""Monitor Stage2 progress."""
import paramiko
import sys
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234', timeout=15)
print("✅ Monitoring Stage2...")

for i in range(30):  # 30 x 15s = 7.5 min
    try:
        stdin, stdout, stderr = ssh.exec_command(
            'nvidia-smi --query-gpu=power.draw,temperature.gpu,memory.used --format=csv,noheader',
            timeout=10
        )
        gpu = stdout.read().decode().strip()
        
        stdin, stdout, stderr = ssh.exec_command(
            'docker logs --tail 5 documusic_backend 2>&1 | grep -E "Stage|V1|error|Error|soundfile|wav|complete"',
            timeout=10
        )
        logs = stdout.read().decode().strip()
        last = [l for l in logs.split('\n') if l.strip()][-1] if logs.strip() else "..."
        
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] GPU: {gpu} | {last[:120]}")
        
        if "complete" in last.lower() or "error" in last.lower() or "saved" in last.lower():
            print("\n🔍 Activity detected! Getting full logs...")
            stdin, stdout, stderr = ssh.exec_command('docker logs --tail 20 documusic_backend 2>&1', timeout=15)
            print(stdout.read().decode())
            
        time.sleep(15)
    except Exception as e:
        print(f"❌ Connection lost: {e}")
        break

ssh.close()
