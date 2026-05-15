"""Check GPU recovery and reboot if needed."""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234')

# Check GPU
print("=== GPU status ===")
stdin, stdout, stderr = ssh.exec_command('nvidia-smi 2>&1 | head -20', timeout=15)
print(stdout.read().decode())

# Check dmesg for GPU errors
print("=== Recent kernel messages ===")
stdin, stdout, stderr = ssh.exec_command('dmesg | tail -20 2>&1', timeout=15)
print(stdout.read().decode())

# Try GPU reset
print("=== Try GPU reset ===")
stdin, stdout, stderr = ssh.exec_command('sudo nvidia-smi --gpu-reset -i 0 2>&1', timeout=30)
print(stdout.read().decode())

time.sleep(5)

# Check again
print("=== GPU after reset ===")
stdin, stdout, stderr = ssh.exec_command('nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader 2>&1', timeout=15)
print(stdout.read().decode())

ssh.close()
print("Done!")
