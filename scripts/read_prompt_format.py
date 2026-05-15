"""Read prompt construction in infer.py."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234')

def run(cmd, timeout=30):
    print(f">>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    if out: print(f"  {out[:1500]}")
    return out

# Read lines 185-250 to see prompt construction
run("docker exec documusic_backend sed -n '185,280p' /opt/YuE/inference/infer.py 2>/dev/null")

# Read lines 280-350 for Stage 1 inference
run("docker exec documusic_backend sed -n '280,350p' /opt/YuE/inference/infer.py 2>/dev/null")

ssh.close()
