#!/usr/bin/env python3
"""
Deploy Watchdog + Prompt Enricher to Madrid server
"""
import paramiko
import time

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"
CONTAINER = "documusic_backend"

def run_cmd(ssh, cmd, timeout=60):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if out:
        print(f"  OUT: {out[:500]}")
    if err:
        print(f"  ERR: {err[:300]}")
    return out, err

def main():
    print("🚀 Deploy Watchdog + Prompt Enricher")
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)
    print("✅ Conectado!")

    # Upload files
    sftp = ssh.open_sftp()
    files = [
        ("backend/main.py", "/tmp/main_watchdog.py"),
        ("backend/gpu_watchdog.py", "/tmp/gpu_watchdog.py"),
        ("backend/prompt_enricher.py", "/tmp/prompt_enricher.py"),
    ]
    for local, remote in files:
        print(f"  Subiendo {local} → {remote}")
        sftp.put(local, remote)
    sftp.close()
    print("✅ Archivos subidos!")

    # Copy to host bind mount
    run_cmd(ssh, "cp /tmp/main_watchdog.py /home/pepe/documusic/backend/main.py")
    run_cmd(ssh, "cp /tmp/gpu_watchdog.py /home/pepe/documusic/backend/gpu_watchdog.py")
    run_cmd(ssh, "cp /tmp/prompt_enricher.py /home/pepe/documusic/backend/prompt_enricher.py")
    
    # Verify
    run_cmd(ssh, "ls -la /home/pepe/documusic/backend/gpu_watchdog.py /home/pepe/documusic/backend/prompt_enricher.py")
    run_cmd(ssh, "grep -n 'start_watchdog\\|enrich_style_prompt\\|can_generate' /home/pepe/documusic/backend/main.py | head -10")
    
    # Restart
    print("\n=== Reiniciando contenedor ===")
    run_cmd(ssh, f"docker restart {CONTAINER}", timeout=30)
    time.sleep(10)
    
    # Check
    run_cmd(ssh, f"docker ps --filter name={CONTAINER} --format '{{{{.Status}}}}'")
    run_cmd(ssh, f"docker exec {CONTAINER} python3 -c \"from gpu_watchdog import start_watchdog, get_watchdog_status; print('✅ gpu_watchdog OK')\"")
    run_cmd(ssh, f"docker exec {CONTAINER} python3 -c \"from prompt_enricher import enrich_style_prompt; print(enrich_style_prompt('American Country'))\"")
    
    # Test GPU endpoint
    time.sleep(3)
    run_cmd(ssh, f"docker exec {CONTAINER} python3 -c \"import urllib.request; r=urllib.request.urlopen('http://localhost:8000/api/gpu'); print(r.read().decode()[:300])\"")
    
    # Test enrich preview endpoint
    run_cmd(ssh, f"docker exec {CONTAINER} python3 -c \"import urllib.request, json; req=urllib.request.Request('http://localhost:8000/api/enrich-preview', data=json.dumps({{'style_prompt':'Rock'}}).encode(), headers={{'Content-Type':'application/json'}}); r=urllib.request.urlopen(req); print(r.read().decode()[:300])\"")
    
    ssh.close()
    print("\n" + "="*60)
    print("✅ WATCHDOG + PROMPT ENRICHER DESPLEGADOS")
    print("="*60)

if __name__ == "__main__":
    main()
