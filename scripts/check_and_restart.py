"""Check server status and restart if needed."""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234')

# 1) Check container status
print("=== Container status ===")
stdin, stdout, stderr = ssh.exec_command('docker ps -a --filter name=documusic_backend --format "{{.Status}}"', timeout=15)
print(stdout.read().decode())

# 2) Check GPU
print("=== GPU ===")
stdin, stdout, stderr = ssh.exec_command('nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader', timeout=15)
print(stdout.read().decode())

# 3) Check last backend logs
print("=== Last 30 backend logs ===")
stdin, stdout, stderr = ssh.exec_command('docker logs documusic_backend --tail 30 2>&1', timeout=15)
print(stdout.read().decode())

# 4) Restart container
print("=== Restarting ===")
stdin, stdout, stderr = ssh.exec_command('docker restart documusic_backend', timeout=30)
print(stdout.read().decode())

time.sleep(15)

# 5) Health check
print("=== Health check ===")
stdin, stdout, stderr = ssh.exec_command('curl -s http://localhost:8000/ | head -c 200', timeout=15)
print(stdout.read().decode())

ssh.close()
print("Done!")
