"""Check current YuE model and investigate anneal-en-cot variant."""
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
    if err: print(f"  ERR: {err[:300]}")
    return out

# Check current model
run("ls -la /root/.cache/huggingface/hub/models--m-a-p--YuE-s1-7B/ 2>/dev/null | head -5")
run("ls -la /opt/YuE/inference/ 2>/dev/null | head -10")

# Check what model ID is used in the code
run("grep -r 'model_name_or_path\\|YuE-s1' /opt/YuE/inference/infer.py 2>/dev/null | head -10")

# Check config of current model
run("cat /root/.cache/huggingface/hub/models--m-a-p--YuE-s1-7B/snapshots/*/config.json 2>/dev/null | head -5")

# Check available YuE models on HuggingFace
run("ls /root/.cache/huggingface/hub/ 2>/dev/null | grep -i yue")

# Check disk space
run("df -h / | tail -1")

ssh.close()
