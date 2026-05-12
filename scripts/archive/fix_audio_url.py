#!/usr/bin/env python3
"""Fix audio URL: mount static files under /api/outputs instead of /outputs"""
import paramiko
import sys

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

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
    
    # Write to a temp file first, then move into the container
    with sftp.open("/tmp/main_fixed.py", "w") as f:
        f.write(main_py_content)
    print("main.py subido a /tmp/main_fixed.py")

    # Copy into the container
    cmds = [
        # Copy the fixed main.py into the running container
        "docker cp /tmp/main_fixed.py documusic-backend-1:/app/main.py",
        # Verify the change
        "docker exec documusic-backend-1 grep -n 'app.mount.*outputs' /app/main.py",
        # Check if there are any MP3 files already generated
        "docker exec documusic-backend-1 ls -la /app/outputs/ 2>/dev/null || echo 'No outputs dir'",
        # Restart the backend container to apply changes
        "docker restart documusic-backend-1",
        # Wait and check it's running
        "sleep 5 && docker ps --filter name=documusic-backend",
    ]

    for cmd in cmds:
        print(f"\n>>> {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        if out:
            print(f"  OUT: {out}")
        if err:
            print(f"  ERR: {err}")

    sftp.close()
    ssh.close()
    print("\nFix aplicado! El backend ahora sirve archivos en /api/outputs/")
    print("El frontend construye URLs como /api/outputs/{id}.mp3 -> proxy -> backend /api/outputs/{id}.mp3")

if __name__ == "__main__":
    main()
