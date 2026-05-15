"""Monitor job progress."""
import paramiko
import time

def run(ssh, cmd, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode().strip()

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.103.141.33", username="pepe", password="pepe1234")

job_id = "030f8349"

for i in range(60):  # Check for up to 30 min
    # Job status
    status = run(ssh, f"curl -s http://localhost:8000/api/job/{job_id}")
    
    # GPU
    gpu = run(ssh, "nvidia-smi --query-gpu=memory.used --format=csv,noheader")
    
    # Subprocess
    proc = run(ssh, "docker exec documusic_backend ps aux | grep infer | grep -v grep | wc -l")
    
    print(f"[{i*30}s] GPU: {gpu} MiB | Proc: {proc} | Status: {status[:200]}")
    
    if '"completed"' in status or '"error"' in status or '"failed"' in status:
        print(f"\n🏁 Job finished!")
        print(status[:1000])
        break
    
    time.sleep(30)

ssh.close()
