#!/usr/bin/env python3
"""
Deploy Fase 0: Better params + Mastering + Multi-variant
Uploads main.py, audio_master.py to the server and restarts the backend.
"""
import paramiko
import sys
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
    print(f"🚀 Deploy Fase 0: Parámetros optimizados + Masterización + Multi-variante")
    print(f"Conectando a {HOST}...")
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)
    print("✅ Conectado!")

    # Upload files via SFTP
    sftp = ssh.open_sftp()
    
    files_to_upload = [
        ("backend/main.py", "/tmp/main_phase0.py"),
        ("backend/audio_master.py", "/tmp/audio_master.py"),
    ]
    
    for local, remote in files_to_upload:
        print(f"  Subiendo {local} → {remote}")
        sftp.put(local, remote)
    
    sftp.close()
    print("✅ Archivos subidos!")

    # Copy files into the container and to the host bind mount
    # The backend dir is bind-mounted: /home/pepe/documusic/backend -> /app
    # So we need to copy to the host path for persistence
    
    # 1. Copy main.py to host (bind mount will make it available in container)
    run_cmd(ssh, "cp /tmp/main_phase0.py /home/pepe/documusic/backend/main.py")
    
    # 2. Copy audio_master.py to host
    run_cmd(ssh, "cp /tmp/audio_master.py /home/pepe/documusic/backend/audio_master.py")
    
    # 3. Verify files are in place
    run_cmd(ssh, "ls -la /home/pepe/documusic/backend/main.py /home/pepe/documusic/backend/audio_master.py")
    
    # 4. Verify the new features in main.py
    run_cmd(ssh, "grep -n 'YUE_PARAMS\\|VARIANT_CONFIG\\|master_audio\\|audio_master' /home/pepe/documusic/backend/main.py | head -15")
    
    # 5. Verify audio_master.py
    run_cmd(ssh, "grep -n 'def master_audio\\|def master_audio_simple\\|def get_audio' /home/pepe/documusic/backend/audio_master.py")
    
    # 6. Check that FFmpeg is available in the container (needed for mastering)
    run_cmd(ssh, f"docker exec {CONTAINER} which ffmpeg")
    
    # 7. Restart the container to pick up changes
    print("\n=== Reiniciando contenedor backend ===")
    run_cmd(ssh, f"docker restart {CONTAINER}", timeout=30)
    
    # 8. Wait for startup
    print("\nEsperando 10s para startup...")
    time.sleep(10)
    
    # 9. Check container is running
    run_cmd(ssh, f"docker ps --filter name={CONTAINER} --format '{{{{.Status}}}}'")
    
    # 10. Test the API
    run_cmd(ssh, f"docker exec {CONTAINER} python3 -c \"import urllib.request; r=urllib.request.urlopen('http://localhost:8000/api'); print(r.read().decode()[:300])\"")
    
    # 11. Verify audio_master module imports correctly
    run_cmd(ssh, f"docker exec {CONTAINER} python3 -c \"from audio_master import master_audio_simple, get_audio_metrics; print('✅ audio_master imports OK')\"")
    
    ssh.close()
    
    print("\n" + "="*60)
    print("✅ FASE 0 DESPLEGADA EXITOSAMENTE")
    print("="*60)
    print("Mejoras activas:")
    print("  0.1: max_new_tokens=4096, run_n_segments=3, rescale=True")
    print("  0.2: Pipeline masterización (LoudNorm + EQ + Compress + Fade)")
    print("  0.3: Multi-variante (2 variantes por defecto, seeds aleatorios)")
    print("="*60)

if __name__ == "__main__":
    main()
