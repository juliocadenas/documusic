#!/usr/bin/env python3
"""Check if bitsandbytes is available in the Docker container."""
import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234', timeout=15)

# Check bitsandbytes
stdin, stdout, stderr = ssh.exec_command('docker exec documusic_backend python3 -c "import bitsandbytes; print(bnb.__version__)" 2>&1', timeout=15)
print("=== BITSANDBYTES ===")
print(stdout.read().decode())

# Check accelerate
stdin, stdout, stderr = ssh.exec_command('docker exec documusic_backend python3 -c "import accelerate; print(accelerate.__version__)" 2>&1', timeout=15)
print("=== ACCELERATE ===")
print(stdout.read().decode())

# Check scipy (needed for some quantization)
stdin, stdout, stderr = ssh.exec_command('docker exec documusic_backend python3 -c "import scipy; print(scipy.__version__)" 2>&1', timeout=15)
print("=== SCIPY ===")
print(stdout.read().decode())

# Quick test: load_in_8bit with a small model
stdin, stdout, stderr = ssh.exec_command('docker exec documusic_backend python3 -c "from transformers import BitsAndBytesConfig; print(BitsAndBytesConfig(load_in_8bit=True))" 2>&1', timeout=15)
print("=== BNB CONFIG TEST ===")
print(stdout.read().decode())

ssh.close()
