"""Check if server is back up after reboot."""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

for attempt in range(12):
    try:
        print(f"Attempt {attempt+1}/12...", end=" ")
        ssh.connect('100.103.141.33', username='pepe', password='pepe1234', timeout=15)
        print("CONNECTED!")
        
        # Check GPU
        stdin, stdout, stderr = ssh.exec_command('nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader 2>&1', timeout=15)
        gpu = stdout.read().decode().strip()
        print(f"GPU: {gpu}")
        
        # Check docker
        stdin, stdout, stderr = ssh.exec_command('docker ps -a --filter name=documusic_backend --format "{{.Status}}" 2>&1', timeout=15)
        docker_status = stdout.read().decode().strip()
        print(f"Docker: {docker_status}")
        
        # Start container if not running
        if 'Up' not in docker_status:
            print("Starting container...")
            stdin, stdout, stderr = ssh.exec_command('docker start documusic_backend 2>&1', timeout=30)
            print(f"Start: {stdout.read().decode().strip()}")
            time.sleep(15)
        
        # Health check
        stdin, stdout, stderr = ssh.exec_command('curl -s http://localhost:8000/ | head -c 300', timeout=15)
        health = stdout.read().decode().strip()
        print(f"Health: {health[:200]}")
        
        ssh.close()
        break
    except Exception as e:
        print(f"failed: {e}")
        time.sleep(15)
else:
    print("All attempts failed. Server may need manual intervention.")
