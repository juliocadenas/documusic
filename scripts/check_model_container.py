"""Check YuE model inside Docker container."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234')

def run(cmd, timeout=30):
    print(f">>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(f"  {out[:500]}")
    if err and 'WARNING' not in err: print(f"  ERR: {err[:300]}")
    return out

# Check model inside container
run("docker exec documusic_backend find / -name 'config.json' -path '*/YuE*' 2>/dev/null | head -5")
run("docker exec documusic_backend ls -la /root/.cache/huggingface/hub/ 2>/dev/null | grep -i yue")
run("docker exec documusic_backend find /root/.cache/huggingface -name 'config.json' 2>/dev/null | head -10")

# Check what model is loaded - look at the infer.py arguments
run("docker exec documusic_backend grep -n 'model_name_or_path\\|pretrained_model_name_or_path\\|YuE' /opt/YuE/inference/infer.py 2>/dev/null | head -20")

# Check the main.py to see what model ID is passed
run("docker exec documusic_backend grep -n 'YuE\\|model.*path\\|7B' /app/main.py 2>/dev/null | head -20")

# Check HuggingFace cache inside container
run("docker exec documusic_backend ls /root/.cache/huggingface/hub/ 2>/dev/null")

# Check if anneal-en-cot model exists
run("docker exec documusic_backend find / -path '*anneal*' -name '*.json' 2>/dev/null | head -5")

ssh.close()
