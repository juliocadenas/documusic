"""Force reboot with sudo password."""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234')

# Reboot with password via stdin
print("=== Sending reboot command ===")
stdin, stdout, stderr = ssh.exec_command('echo pepe1234 | sudo -S reboot now', timeout=10)
try:
    out = stdout.read().decode()
    err = stderr.read().decode()
    print(f"out: {out}")
    print(f"err: {err}")
except:
    pass

ssh.close()
print("Reboot sent. Server will go down in a few seconds.")
print("Waiting 90 seconds for full reboot...")

time.sleep(90)

# Try to reconnect
for attempt in range(8):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect('100.103.141.33', username='pepe', password='pepe1234', timeout=10)
        
        print(f"\n=== Connected (attempt {attempt+1}) ===")
        
        # Check GPU
        stdin, stdout, stderr = ssh.exec_command('nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader 2>&1', timeout=15)
        gpu = stdout.read().decode()
        print(f"GPU: {gpu.strip()}")
        
        if 'MiB' in gpu:
            print("GPU is back!")
            
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
