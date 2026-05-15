"""Quick job status check."""
import paramiko

def run(ssh, cmd, timeout=15):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode().strip()

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.103.141.33", username="pepe", password="pepe1234")

job_id = "dbee957c"
status = run(ssh, f"curl -s http://localhost:8000/api/job/{job_id}")
gpu = run(ssh, "nvidia-smi --query-gpu=memory.used --format=csv,noheader")
proc = run(ssh, "docker exec documusic_backend ps aux | grep infer | grep -v grep | wc -l")

print(f"GPU: {gpu} MiB | Process: {proc}")
print(f"Status: {status[:1000]}")

ssh.close()
