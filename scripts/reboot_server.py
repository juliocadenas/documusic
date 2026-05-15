"""Reboot server to recover GPU driver."""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234')

print("=== Rebooting server ===")
stdin, stdout, stderr = ssh.exec_command('sudo reboot', timeout=10)
try:
    print(stdout.read().decode())
except:
    pass

ssh.close()
print("Reboot command sent. Waiting 60s for server to come back...")

time.sleep(60)

# Try to reconnect
for attempt in range(5):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect('100.103.141.33', username='pepe', password='pepe1234', timeout=10)
        
        print(f"\n=== Connected (attempt {attempt+1}) ===")
        
        # Check GPU
        stdin, stdout, stderr = ssh.exec_command('nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader 2>&1', timeout=15)
        gpu = stdout.read().decode()
        print(f"GPU: {gpu.strip()}")
        
        # Start container
        stdin, stdout, stderr = ssh.exec_command('docker start documusic_backend 2>&1', timeout=30)
        print(f"Container: {stdout.read().decode().strip()}")
        
        time.sleep(15)
        
        # Health check
        stdin, stdout, stderr = ssh.exec_command('curl -s http://localhost:8000/ | head -c 200', timeout=15)
        health = stdout.read().decode()
        print(f"Health: {health[:150]}")
        
        ssh.close()
        break
    except Exception as e:
        print(f"  Attempt {attempt+1} failed: {e}")
        time.sleep(15)

print("\nDone!")
