"""Check YuE model variant and find prompt examples."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234')

# 1) Check what s1 model we have
print("=== Model files ===")
stdin, stdout, stderr = ssh.exec_command('ls -la /home/pepe/AI_MODELS/huggingface/YuE-s1/ 2>/dev/null | head -20', timeout=15)
print(stdout.read().decode())

# Check config.json for model name
stdin, stdout, stderr = ssh.exec_command('cat /home/pepe/AI_MODELS/huggingface/YuE-s1/config.json 2>/dev/null | head -20', timeout=15)
print("=== s1 config.json ===")
print(stdout.read().decode())

# 2) Find prompt_egs
print("=== Find prompt examples ===")
stdin, stdout, stderr = ssh.exec_command('find /home/pepe/AI_MODELS/huggingface/ -path "*/prompt*" -type f 2>/dev/null; find /opt/YuE -path "*/prompt*" -type f 2>/dev/null | head -20', timeout=15)
print(stdout.read().decode())

# 3) Read the split_lyrics function from infer.py
print("=== split_lyrics function ===")
stdin, stdout, stderr = ssh.exec_command('docker exec documusic_backend sed -n "185,195p" /opt/YuE/inference/infer.py', timeout=15)
print(stdout.read().decode())

# 4) Read the prompt construction section
print("=== Prompt construction (lines 195-210) ===")
stdin, stdout, stderr = ssh.exec_command('docker exec documusic_backend sed -n "195,210p" /opt/YuE/inference/infer.py', timeout=15)
print(stdout.read().decode())

# 5) Check if there are example lyrics files anywhere
print("=== Find any .txt files in YuE ===")
stdin, stdout, stderr = ssh.exec_command('find /opt/YuE -name "*.txt" -type f 2>/dev/null | head -20', timeout=15)
print(stdout.read().decode())

# 6) Read top_200_tags.json for vocal-related tags
print("=== Vocal-related tags from top_200_tags.json ===")
stdin, stdout, stderr = ssh.exec_command('docker exec documusic_backend python3 -c "import json; tags=json.load(open(\'/opt/YuE/top_200_tags.json\')); vocal=[t for t in tags if \'voc\' in t.lower() or \'sing\' in t.lower() or \'male\' in t.lower() or \'femal\' in t.lower()]; print(vocal)"', timeout=15)
print(stdout.read().decode())

ssh.close()
