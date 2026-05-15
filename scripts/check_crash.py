"""Check server status after Stage 2 crash."""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect('100.103.141.33', username='pepe', password='pepe1234', timeout=15)
    print("=== SERVER REACHABLE ===")
    
    # Check GPU
    stdin, stdout, stderr = ssh.exec_command('nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader 2>&1', timeout=15)
    gpu = stdout.read().decode().strip()
    print(f"GPU: {gpu}")
    
    # Check if backend container is running
    stdin, stdout, stderr = ssh.exec_command('docker ps -a --filter name=documusic_backend --format "{{.Status}}" 2>&1', timeout=15)
    docker = stdout.read().decode().strip()
    print(f"Docker: {docker}")
    
    # Check backend logs - last 80 lines
    stdin, stdout, stderr = ssh.exec_command('docker logs documusic_backend --tail 80 2>&1', timeout=15)
    logs = stdout.read().decode()
    print(f"\n=== LAST 80 LOG LINES ===\n{logs}")
    
    ssh.close()
except Exception as e:
    print(f"Cannot connect: {e}")
