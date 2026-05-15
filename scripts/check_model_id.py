"""Check which YuE model variant is installed."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234')

def run(cmd, timeout=30):
    print(f">>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    if out: print(f"  {out[:800]}")
    return out

# Check model config
run("docker exec documusic_backend cat /app/models/YuE-s1/config.json 2>/dev/null | head -20")

# Check model name in config
run("docker exec documusic_backend python3 -c \"import json; c=json.load(open('/app/models/YuE-s1/config.json')); print('_name_or_path:', c.get('_name_or_path','N/A')); print('model_type:', c.get('model_type','N/A')); print('vocab_size:', c.get('vocab_size','N/A'))\" 2>/dev/null")

# Check README or model card
run("docker exec documusic_backend ls -la /app/models/YuE-s1/ 2>/dev/null | head -15")

# Check total size
run("docker exec documusic_backend du -sh /app/models/YuE-s1/ 2>/dev/null")

# Check if there's a model.safetensors or pytorch bin files
run("docker exec documusic_backend ls /app/models/YuE-s1/*.safetensors /app/models/YuE-s1/*.bin 2>/dev/null | head -10")

# Check if there's a README
run("docker exec documusic_backend cat /app/models/YuE-s1/README.md 2>/dev/null | head -20")

ssh.close()
