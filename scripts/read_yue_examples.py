"""Read YuE prompt examples to understand correct lyrics format for vocal generation."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234')

# List prompt_egs directory
print("=== Prompt examples directory ===")
stdin, stdout, stderr = ssh.exec_command('docker exec documusic_backend find /opt/YuE/prompt_egs -type f 2>/dev/null | head -20', timeout=15)
print(stdout.read().decode())

# Read genre and lyrics examples
for example_dir in ['prompt_egs', 'prompt_egs/prompt_egs']:
    for ext in ['txt']:
        for name in ['genre', 'lyrics', 'genre1', 'lyrics1', 'genre_txt', 'lyrics_txt']:
            for path in [f'/opt/YuE/{example_dir}/{name}.{ext}', f'/opt/YuE/inference/{example_dir}/{name}.{ext}']:
                stdin, stdout, stderr = ssh.exec_command(f'docker exec documusic_backend cat {path} 2>/dev/null', timeout=15)
                content = stdout.read().decode()
                if content:
                    print(f"\n=== {path} ===")
                    print(content[:1000])

# Also check README for instructions
stdin, stdout, stderr = ssh.exec_command('docker exec documusic_backend cat /opt/YuE/README.md 2>/dev/null | head -200', timeout=15)
readme = stdout.read().decode()
if readme:
    print("\n=== README (first 200 lines) ===")
    print(readme[:3000])

ssh.close()
