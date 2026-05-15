#!/usr/bin/env python3
"""SSH al servidor Madrid: aplicar power limit 200W, verificar FS, reiniciar backend."""
import paramiko
import sys
import time

HOST = "100.103.141.33"
USER = "pepe"
PASS = "pepe1234"

def run_cmd(ssh, cmd, timeout=30):
    """Ejecuta comando y retorna stdout/stderr."""
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    exit_code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip())
    if err.strip():
        print(f"[STDERR] {err.strip()}")
    print(f"[EXIT CODE: {exit_code}]")
    return out, err, exit_code

def main():
    print(f"Conectando a {USER}@{HOST}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(HOST, username=USER, password=PASS, timeout=15)
        print("✅ Conexión SSH establecida")
    except Exception as e:
        print(f"❌ No se pudo conectar: {e}")
        sys.exit(1)

    # 1. Verificar que el servidor está vivo
    run_cmd(ssh, "uptime")
    run_cmd(ssh, "hostname")

    # 2. Verificar GPU
    run_cmd(ssh, "nvidia-smi --query-gpu=name,power.limit,power.draw,temperature.gpu,memory.used,memory.total --format=csv")

    # 3. Aplicar power limit 200W
    print("\n" + "="*50)
    print("APLICANDO POWER LIMIT 200W...")
    print("="*50)
    out, err, code = run_cmd(ssh, "echo pepe1234 | sudo -S nvidia-smi -pl 200")
    
    # Verificar que se aplicó
    run_cmd(ssh, "nvidia-smi --query-gpu=power.limit --format=csv,noheader")

    # 4. Verificar filesystem
    print("\n" + "="*50)
    print("VERIFICANDO FILESYSTEM...")
    print("="*50)
    out, err, code = run_cmd(ssh, "touch /tmp/test_write 2>&1 && echo 'FS_OK' || echo 'FS_READONLY'")
    if "FS_READONLY" in out:
        print("⚠️ Filesystem read-only, remontando...")
        run_cmd(ssh, "echo pepe1234 | sudo -S mount -o remount,rw /")
    
    # 5. Verificar Docker
    print("\n" + "="*50)
    print("VERIFICANDO DOCKER...")
    print("="*50)
    run_cmd(ssh, "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'")

    # 6. Pull latest code
    print("\n" + "="*50)
    print("ACTUALIZANDO CÓDIGO...")
    print("="*50)
    run_cmd(ssh, "cd ~/documusic && git pull")

    # 7. Reiniciar backend
    print("\n" + "="*50)
    print("REINICIANDO BACKEND...")
    print("="*50)
    run_cmd(ssh, "cd ~/documusic && docker compose restart documusic_backend", timeout=60)

    # 8. Esperar y verificar
    print("\nEsperando 10s para que el backend arranque...")
    time.sleep(10)
    run_cmd(ssh, "docker logs --tail 20 documusic_backend")

    # 9. Verificar endpoint
    print("\n" + "="*50)
    print("VERIFICANDO ENDPOINT...")
    print("="*50)
    run_cmd(ssh, "curl -s http://localhost:8000/ | head -5")

    print("\n" + "="*50)
    print("✅ SETUP COMPLETADO - Power limit 200W aplicado")
    print("🚀 Listo para probar generación desde el frontend")
    print("="*50)

    ssh.close()

if __name__ == "__main__":
    main()
