"""Check which YuE model variant we have and read prompt_egs."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234')

# 1) Check model safetensors for any identifying info
print("=== Model index ===")
stdin, stdout, stderr = ssh.exec_command('head -20 /home/pepe/AI_MODELS/huggingface/YuE-s1/model.safetensors.index.json 2>/dev/null', timeout=15)
print(stdout.read().decode())

# 2) Check all files in model dir
print("=== Model dir files ===")
stdin, stdout, stderr = ssh.exec_command('ls -la /home/pepe/AI_MODELS/huggingface/YuE-s1/ 2>/dev/null', timeout=15)
print(stdout.read().decode())

# 3) Check tokenizer special tokens
print("=== Tokenizer info ===")
cmd = 'docker exec documusic_backend python3 -c "import sys; sys.path.insert(0, \\"/opt/YuE/inference\\"); from mm_tokenizer import _MMSentencePieceTokenizer; t = _MMSentencePieceTokenizer(\\"/opt/YuE/inference/mm_tokenizer_v0.2_hf/tokenizer.model\\"); print(\\"vocab:\\", t.vocab_size, \\"soa:\\", t.soa, \\"eoa:\\", t.eoa)" 2>&1'
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
print(stdout.read().decode())

# 4) Read prompt_egs from YuE repo
print("=== Find prompt_egs ===")
stdin, stdout, stderr = ssh.exec_command('find /opt/YuE -name "genre*" -o -name "lyrics*" 2>/dev/null | head -20', timeout=15)
files = stdout.read().decode()
print(files)

for path in ['/opt/YuE/prompt_egs/genre.txt', '/opt/YuE/prompt_egs/lyrics.txt',
             '/opt/YuE/inference/prompt_egs/genre.txt', '/opt/YuE/inference/prompt_egs/lyrics.txt',
             '/opt/YuE/prompt_egs/prompt_egs/genre.txt', '/opt/YuE/prompt_egs/prompt_egs/lyrics.txt']:
    stdin, stdout, stderr = ssh.exec_command(f'docker exec documusic_backend cat {path} 2>/dev/null', timeout=15)
    content = stdout.read().decode()
    if content:
        print(f'\n=== {path} ===')
        print(content[:500])

# 5) Check the README prompt engineering section
print("=== Prompt engineering guide ===")
stdin, stdout, stderr = ssh.exec_command('docker exec documusic_backend grep -A 50 "prompt engineering" /opt/YuE/README.md 2>/dev/null | head -60', timeout=15)
print(stdout.read().decode())

# 6) Check last generation output for vocal/inst tracks
print("=== Last output dir contents ===")
stdin, stdout, stderr = ssh.exec_command('docker exec documusic_backend find /app/outputs -name "*track*" -o -name "*.npy" 2>/dev/null | head -20', timeout=15)
print(stdout.read().decode())

ssh.close()
