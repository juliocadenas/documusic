"""Read YuE infer.py to understand expected input format for anneal-en-cot."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234')

def run(cmd, timeout=30):
    print(f">>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    if out: print(f"  {out[:1000]}")
    return out

# Read the input processing part of infer.py
run("docker exec documusic_backend head -150 /opt/YuE/inference/infer.py 2>/dev/null")

# Check how genre_txt and lyrics_txt are read
run("docker exec documusic_backend grep -n 'genre\\|lyrics\\|read_text\\|open.*txt' /opt/YuE/inference/infer.py 2>/dev/null | head -20")

# Check the prompt construction
run("docker exec documusic_backend sed -n '100,200p' /opt/YuE/inference/infer.py 2>/dev/null")

# Check what the actual genre.txt and lyrics.txt look like for the latest generation
run("docker exec documusic_backend find /app/outputs -name 'style.txt' -newer /app/outputs -mmin -30 2>/dev/null | head -3")
run("docker exec documusic_backend find /app/outputs -name 'lyrics.txt' -newer /app/outputs -mmin -30 2>/dev/null | head -3")

# Read the most recent style.txt and lyrics.txt
run("docker exec documusic_backend find /tmp/documusic_* -name 'style.txt' 2>/dev/null | head -1 | xargs -I{} cat {} 2>/dev/null")
run("docker exec documusic_backend find /tmp/documusic_* -name 'lyrics.txt' 2>/dev/null | head -1 | xargs -I{} cat {} 2>/dev/null")

ssh.close()
