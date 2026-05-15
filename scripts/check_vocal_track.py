"""Check vocal tags and verify last output's vocal track content."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234')

# 1) Read top_200_tags.json fully - gender and timbre categories
print("=== Gender tags ===")
stdin, stdout, stderr = ssh.exec_command('''docker exec documusic_backend python3 -c "import json; d=json.load(open('/opt/YuE/top_200_tags.json')); print('gender:', d.get('gender', [])); print('timbre:', d.get('timbre', [])); print('genre:', d.get('genre', [])[:20]); print('mood:', d.get('mood', [])[:20])"''', timeout=15)
print(stdout.read().decode())

# 2) Check last output - find vocal track files
print("=== Last output vocal tracks ===")
stdin, stdout, stderr = ssh.exec_command('find /home/pepe/documusic/outputs/f7169549 -name "*vtrack*" -o -name "*itrack*" 2>/dev/null', timeout=15)
print(stdout.read().decode())

# 3) Check if vocal track has actual content (non-zero)
print("=== Check vocal vs instrumental track sizes ===")
stdin, stdout, stderr = ssh.exec_command('''docker exec documusic_backend python3 -c "
import numpy as np, os, glob
# Find the most recent output
outputs_dir = '/app/outputs'
dirs = sorted([d for d in os.listdir(outputs_dir) if os.path.isdir(os.path.join(outputs_dir, d))])
if dirs:
    last = os.path.join(outputs_dir, dirs[-1])
    vtracks = glob.glob(os.path.join(last, '**', '*vtrack*'), recursive=True)
    itracks = glob.glob(os.path.join(last, '**', '*itrack*'), recursive=True)
    for v in vtracks:
        data = np.load(v)
        print(f'Vocal: {os.path.basename(v)} shape={data.shape} min={data.min():.4f} max={data.max():.4f} mean={abs(data).mean():.6f}')
    for i in itracks:
        data = np.load(i)
        print(f'Inst: {os.path.basename(i)} shape={data.shape} min={data.min():.4f} max={data.max():.4f} mean={abs(data).mean():.6f}')
" 2>&1''', timeout=30)
print(stdout.read().decode())

# 4) Check what model files we have
print("=== Model s1 files ===")
stdin, stdout, stderr = ssh.exec_command('ls /home/pepe/AI_MODELS/huggingface/YuE-s1/*.json 2>/dev/null; head -3 /home/pepe/AI_MODELS/huggingface/YuE-s1/config.json 2>/dev/null', timeout=15)
print(stdout.read().decode())

# 5) Check generation_config.json for model name
stdin, stdout, stderr = ssh.exec_command('cat /home/pepe/AI_MODELS/huggingface/YuE-s1/generation_config.json 2>/dev/null', timeout=15)
print("=== generation_config ===")
print(stdout.read().decode())

# 6) Check the README for model download instructions
print("=== README model section ===")
stdin, stdout, stderr = ssh.exec_command('docker exec documusic_backend grep -A 20 "Model Weights" /opt/YuE/README.md 2>/dev/null || docker exec documusic_backend grep -A 20 "Hugging Face" /opt/YuE/README.md 2>/dev/null || docker exec documusic_backend grep -A 20 "download" /opt/YuE/README.md 2>/dev/null | head -30', timeout=15)
print(stdout.read().decode())

ssh.close()
