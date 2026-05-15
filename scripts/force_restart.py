"""Force restart container to clear CUDA context."""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234')

# Stop container completely, then start (not just restart)
print("=== Stopping container ===")
stdin, stdout, stderr = ssh.exec_command('docker stop documusic_backend', timeout=30)
print(stdout.read().decode())

time.sleep(3)

# Check GPU is free
print("=== GPU status ===")
stdin, stdout, stderr = ssh.exec_command('nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader', timeout=15)
print(stdout.read().decode())

# Check for zombie processes on GPU
print("=== GPU processes ===")
stdin, stdout, stderr = ssh.exec_command('nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv,noheader 2>&1', timeout=15)
print(stdout.read().decode())

# Start container
print("=== Starting container ===")
stdin, stdout, stderr = ssh.exec_command('docker start documusic_backend', timeout=30)
print(stdout.read().decode())

time.sleep(15)

# Health check
print("=== Health check ===")
stdin, stdout, stderr = ssh.exec_command('curl -s http://localhost:8000/ | head -c 200', timeout=15)
print(stdout.read().decode())

ssh.close()
print("Done!")
