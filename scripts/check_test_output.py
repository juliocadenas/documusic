"""Quick check on test_official output files."""
import paramiko

def run(ssh, cmd, timeout=15):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip(): print(f"  ← {out.strip()[:2000]}")
    if err.strip(): print(f"  ⚠ {err.strip()[:300]}")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.103.141.33", username="pepe", password="pepe1234")

# Check if test_official output exists
print("=== Test official output files ===")
run(ssh, "docker exec documusic_backend find /app/outputs/test_official/ -name '*.wav' -exec ls -la {} \\; 2>/dev/null | head -20")

# Check volume levels
print("\n=== Volume levels ===")
run(ssh, """docker exec documusic_backend bash -c 'find /app/outputs/test_official/ -name "*vtrack*.wav" -type f | while read f; do echo "vtrack: $f"; ffmpeg -i "$f" -af volumedetect -f null /dev/null 2>&1 | grep -i "mean_volume\\|max_volume"; done'""")
run(ssh, """docker exec documusic_backend bash -c 'find /app/outputs/test_official/ -name "*itrack*.wav" -type f | while read f; do echo "itrack: $f"; ffmpeg -i "$f" -af volumedetect -f null /dev/null 2>&1 | grep -i "mean_volume\\|max_volume"; done'""")

# Check if process is still running
print("\n=== Running processes ===")
run(ssh, "docker exec documusic_backend ps aux | grep infer | grep -v grep")

# Check GPU
print("\n=== GPU ===")
run(ssh, "nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader")

ssh.close()
print("\n🏁 Done!")
