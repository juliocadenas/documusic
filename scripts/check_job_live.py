"""Check if the generation job is still running."""
import paramiko
import json

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234')

# Check job status via API
stdin, stdout, stderr = ssh.exec_command('curl -s http://localhost:8000/ 2>&1', timeout=15)
health = stdout.read().decode().strip()
print(f"Health: {health[:200]}")

# Get all recent docker logs
stdin, stdout, stderr = ssh.exec_command('docker logs documusic_backend --tail 30 2>&1 | grep -v "GET /api"', timeout=15)
logs = stdout.read().decode()
print(f"\n=== Recent logs (no GET requests) ===\n{logs}")

# Check GPU usage
stdin, stdout, stderr = ssh.exec_command('nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader 2>&1', timeout=15)
gpu = stdout.read().decode().strip()
print(f"\nGPU: {gpu}")

# Check if there's output files
stdin, stdout, stderr = ssh.exec_command('ls -la /tmp/documusic_* 2>/dev/null; find /tmp -name "*.wav" -newer /tmp -mmin -30 2>/dev/null | head -5', timeout=15)
files = stdout.read().decode().strip()
print(f"\nFiles: {files}")

ssh.close()
