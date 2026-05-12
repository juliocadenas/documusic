#!/usr/bin/env python3
"""Fix audio URL: mount static files under /api/outputs instead of /outputs"""
import paramiko
import sys

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

def run_cmd(ssh, cmd, timeout=60):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if out:
        print(f"  OUT: {out}")
    if err:
        print(f"  ERR: {err}")
    return out, err

def main():
    print(f"Conectando a {HOST}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)
    print("Conectado!")

    # Read the fixed main.py
    with open("backend/main.py", "r", encoding="utf-8") as f:
        main_py_content = f.read()

    # Upload via SFTP
    sftp = ssh.open_sftp()
    with sftp.open("/tmp/main_fixed.py", "w") as f:
        f.write(main_py_content)
    print("main.py subido a /tmp/main_fixed.py")
    sftp.close()

    # The container name is documusic_backend (no hyphen)
    CONTAINER = "documusic_backend"

    # Copy the fixed main.py into the running container
    run_cmd(ssh, f"docker cp /tmp/main_fixed.py {CONTAINER}:/app/main.py")
    
    # Verify the change
    run_cmd(ssh, f"docker exec {CONTAINER} grep -n 'app.mount.*outputs' /app/main.py")
    
    # Check existing MP3 files in outputs
    run_cmd(ssh, f"docker exec {CONTAINER} ls -la /app/outputs/ 2>/dev/null | head -20")
    
    # Also check what the current main.py on the host looks like (for docker-compose rebuilds)
    run_cmd(ssh, "grep -n 'app.mount.*outputs' /home/pepe/documusic/backend/main.py 2>/dev/null || echo 'Not found in host'")
    
    # Copy to the host too so it persists across rebuilds
    run_cmd(ssh, "cp /tmp/main_fixed.py /home/pepe/documusic/backend/main.py")
    run_cmd(ssh, "grep -n 'app.mount.*outputs' /home/pepe/documusic/backend/main.py")

    # Restart the backend container to apply changes
    print("\n=== Reiniciando el contenedor backend ===")
    run_cmd(ssh, f"docker restart {CONTAINER}", timeout=30)
    
    # Wait and check it's running
    import time
    time.sleep(8)
    run_cmd(ssh, f"docker ps --filter name={CONTAINER}")
    
    # Test the endpoint
    time.sleep(5)
    run_cmd(ssh, f"docker exec {CONTAINER} python -c \"import requests; r=requests.get('http://localhost:8000/'); print(r.json())\"", timeout=15)
    
    # Check if we can access the outputs via the new path
    run_cmd(ssh, f"docker exec {CONTAINER} ls /app/outputs/*.mp3 2>/dev/null | head -5")

    ssh.close()
    print("\n✅ Fix aplicado! El backend ahora sirve archivos en /api/outputs/")
    print("URL flow: Frontend -> /api/outputs/{id}.mp3 -> Vite proxy -> Backend /api/outputs/{id}.mp3")

if __name__ == "__main__":
    main()
