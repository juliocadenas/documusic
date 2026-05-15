"""Read YuE top_200_tags.json and prompt examples to understand tag format."""
import paramiko

def run(ssh, cmd, timeout=30):
    print(f"\n>>> {cmd}")
    try:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode('utf-8', errors='replace').strip()
        if out:
            print(out[:5000])
        return out
    except Exception as e:
        print(f"[ERROR] {e}")
        return ""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234')

# 1. Read top_200_tags.json
print("=" * 60)
print("YuE TOP 200 TAGS")
print("=" * 60)
run(ssh, "docker exec documusic_backend cat /opt/YuE/top_200_tags.json")

# 2. Read prompt examples
print("\n" + "=" * 60)
print("YuE PROMPT EXAMPLES")
print("=" * 60)
run(ssh, "ls /opt/YuE/prompt_egs/ 2>/dev/null")
run(ssh, "docker exec documusic_backend ls /opt/YuE/prompt_egs/ 2>/dev/null")
run(ssh, "docker exec documusic_backend find /opt/YuE/prompt_egs/ -name '*.txt' -exec cat {} \\; 2>/dev/null | head -100")

# 3. Read infer.py to understand prompt format
print("\n" + "=" * 60)
print("YuE INFER.PY - PROMPT HANDLING")
print("=" * 60)
run(ssh, "docker exec documusic_backend grep -n 'Genre\\|Lyrics\\|prompt\\|tags\\|genre' /opt/YuE/inference/infer.py | head -40")

ssh.close()
print("\nDone.")
