"""Monitor generation progress - wait for completion."""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234')

print("Monitoring generation progress...")

for i in range(30):  # Check every 30s for up to 15 minutes
    # Check GPU
    stdin, stdout, stderr = ssh.exec_command('nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader 2>&1', timeout=15)
    gpu = stdout.read().decode().strip()
    
    # Check for output files
    stdin, stdout, stderr = ssh.exec_command('ls -lt /tmp/documusic_*/output* 2>/dev/null; ls -lt /tmp/documusic_*/*.wav 2>/dev/null; ls -lt /tmp/documusic_*/*.mp3 2>/dev/null', timeout=15)
    files = stdout.read().decode().strip()
    
    # Check recent logs (no GET requests)
    stdin, stdout, stderr = ssh.exec_command('docker logs documusic_backend --tail 5 2>&1 | grep -v "GET /api" | grep -v "^$"', timeout=15)
    logs = stdout.read().decode().strip()
    
    print(f"\n[{i*30}s] GPU: {gpu}")
    if files:
        print(f"  FILES: {files[:300]}")
    if logs:
        print(f"  LOGS: {logs[:300]}")
    
    # Check if generation completed
    if 'done' in logs.lower() or 'error' in logs.lower() or files:
        if files:
            print("\n=== GENERATION COMPLETE - Files found! ===")
            # Get full file listing
            stdin, stdout, stderr = ssh.exec_command('find /tmp/documusic_* -type f -name "*.wav" -o -name "*.mp3" 2>/dev/null | head -10', timeout=15)
            all_files = stdout.read().decode().strip()
            print(f"All output files:\n{all_files}")
            break
    
    if 'CUDA' in logs or 'Error' in logs or 'OOM' in logs:
        print(f"\n=== ERROR DETECTED ===")
        stdin, stdout, stderr = ssh.exec_command('docker logs documusic_backend --tail 30 2>&1 | grep -v "GET /api"', timeout=15)
        error_logs = stdout.read().decode()
        print(error_logs)
        break
    
    time.sleep(30)

ssh.close()
