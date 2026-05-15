"""Deploy pollJob fix: git pull + docker restart."""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234')

def run(cmd, timeout=60):
    print(f">>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(f"  OUT: {out[:300]}")
    if err: print(f"  ERR: {err[:300]}")
    return out, err

# Git pull
run("cd ~/documusic && git pull")

# Restart container
run("docker restart documusic_backend")

print("\nWaiting 15s for backend to start...")
time.sleep(15)

# Health check
run("curl -s http://localhost:8000/ | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8000/")

ssh.close()
print("\nDeploy complete!")
