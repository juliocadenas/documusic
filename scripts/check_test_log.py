"""Quick check of test log to debug failure."""
import paramiko

def run(ssh, cmd, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out.strip(): print(out[-2000:])
    if err.strip(): print(f"ERR: {err[-500:]}")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.103.141.33", username="pepe", password="pepe1234")

print("=== T1 Log (last 50 lines) ===")
run(ssh, "docker exec documusic_backend tail -50 /app/outputs/param_test/T1_tok3000_seg1/log.txt 2>/dev/null")

print("\n=== T2 Log (last 10 lines) ===")
run(ssh, "docker exec documusic_backend tail -10 /app/outputs/param_test/T2_tok3000_seg2/log.txt 2>/dev/null")

print("\n=== Running processes ===")
run(ssh, "docker exec documusic_backend ps aux | grep infer | grep -v grep")

print("\n=== GPU ===")
run(ssh, "nvidia-smi --query-gpu=memory.used --format=csv,noheader")

ssh.close()
