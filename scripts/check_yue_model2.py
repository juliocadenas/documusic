"""Deep check: model variant, top_200_tags content, and last generation files."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234')

# 1) Check model config
print("=== Model config.json ===")
stdin, stdout, stderr = ssh.exec_command('cat /home/pepe/AI_MODELS/huggingface/YuE-s1/config.json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get(\'_name_or_path\',\'N/A\')); print(\'model_type:\', d.get(\'model_type\',\'N/A\'))" 2>/dev/null', timeout=15)
print(stdout.read().decode())

# Check model name from pretrained config  
stdin, stdout, stderr = ssh.exec_command('docker exec documusic_backend cat /app/models/YuE-s1/config.json 2>/dev/null | head -5', timeout=15)
print("=== Config from container ===")
print(stdout.read().decode())

# 2) Read top_200_tags.json fully
print("=== top_200_tags.json (first 50) ===")
stdin, stdout, stderr = ssh.exec_command('docker exec documusic_backend python3 -c "import json; tags=json.load(open(\'/opt/YuE/top_200_tags.json\')); print(type(tags)); print(len(tags) if isinstance(tags, list) else \'dict\'); [print(t) for t in (tags[:50] if isinstance(tags, list) else list(tags.keys())[:50])]"', timeout=15)
print(stdout.read().decode())

# 3) Check last generation output files
print("=== Last outputs ===")
stdin, stdout, stderr = ssh.exec_command('ls -la /home/pepe/documusic/outputs/ 2>/dev/null | tail -10', timeout=15)
print(stdout.read().decode())

# 4) Check stage1 output for vocal tracks
print("=== Stage1 output dirs ===")
stdin, stdout, stderr = ssh.exec_command('docker exec documusic_backend find /tmp -name "*vtrack*" -o -name "*itrack*" 2>/dev/null | head -10', timeout=15)
print(stdout.read().decode())

# 5) Check the actual patched infer.py lines 130-150 for model loading
print("=== Model loading (lines 130-150) ===")
stdin, stdout, stderr = ssh.exec_command('docker exec documusic_backend sed -n "130,155p" /opt/YuE/inference/infer.py', timeout=15)
print(stdout.read().decode())

# 6) Check lines 280-310 for vocal extraction
print("=== Vocal extraction (lines 280-310) ===")
stdin, stdout, stderr = ssh.exec_command('docker exec documusic_backend sed -n "280,310p" /opt/YuE/inference/infer.py', timeout=15)
print(stdout.read().decode())

ssh.close()
