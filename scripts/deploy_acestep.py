"""Deploy ACE-Step integration: git pull + create dirs + docker compose up."""
import paramiko
import time

HOST = "100.103.141.33"
USER = "pepe"
PASS = "pepe1234"

def run(ssh, cmd, timeout=60):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip()[-2000:])
    if err.strip():
        print(f"STDERR: {err.strip()[-1000:]}")
    return out, err, code

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)
print(f"✅ Connected to {HOST}")

# 1. Git pull
run(ssh, "cd ~/documusic && git pull")

# 2. Create ACE-Step directory on host (for volume mount)
run(ssh, "mkdir -p /home/pepe/AI_MODELS/ace-step")

# 3. Docker compose up (to pick up new volume mount)
run(ssh, "cd ~/documusic && docker compose up -d documusic_backend", timeout=60)

# 4. Wait for container to start
print("\n⏳ Waiting 15s for container to start...")
time.sleep(15)

# 5. Check container is running
run(ssh, "docker ps --filter name=documusic_backend --format '{{.Status}}'")

# 6. Check startup logs for ACE-Step setup
out, err, code = run(ssh, "docker logs documusic_backend --tail 40 2>&1")
print("\n" + "="*60)
print("RECENT LOGS:")
print("="*60)
print(out[-3000:] if len(out) > 3000 else out)

# 7. Check if ACE-Step is being installed (first time takes a while)
if "Clonando ACE-Step" in out or "Instalando ACE-Step" in out:
    print("\n⏳ ACE-Step está siendo instalado (primera vez). Esto puede tardar varios minutos...")
    print("   Esperando 60s y verificando de nuevo...")
    time.sleep(60)
    out, err, code = run(ssh, "docker logs documusic_backend --tail 20 2>&1")
    print(out[-2000:])

# 8. Verify volume mount
run(ssh, "docker exec documusic_backend ls /opt/ACE-Step/ 2>/dev/null || echo 'ACE-Step dir empty or not mounted'")

# 9. Verify models available
out, err, code = run(ssh, "docker exec documusic_backend python3 -c \"import requests; r=requests.get('http://localhost:8000/'); print(r.json().get('models_available', 'N/A'))\" 2>&1 || echo 'API not ready yet'")

ssh.close()
print("\n✅ Deploy completado!")
