"""
Script de despliegue automático para DocuMusic
Sube los archivos corregidos al servidor Madrid y reconstruye el contenedor.
"""
import paramiko
import os
import sys
import time

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"
REMOTE_DIR = "/home/pepe/documusic"

# Archivos a subir (ruta local -> ruta remota)
FILES_TO_UPLOAD = [
    ("backend/main.py", f"{REMOTE_DIR}/backend/main.py"),
    ("frontend/src/App.jsx", f"{REMOTE_DIR}/frontend/src/App.jsx"),
    ("docker-compose.yml", f"{REMOTE_DIR}/docker-compose.yml"),
]


def create_ssh_client():
    """Crea conexión SSH con el servidor."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"🔗 Conectando a {HOST}...")
    client.connect(HOST, username=USER, password=PASS, timeout=15)
    print(f"✅ Conectado a {HOST}")
    return client


def run_command(client, cmd, timeout=120):
    """Ejecuta un comando remoto y muestra la salida."""
    print(f"\n🔧 Ejecutando: {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()

    if out.strip():
        print(f"  STDOUT: {out.strip()[:500]}")
    if err.strip():
        print(f"  STDERR: {err.strip()[:500]}")
    print(f"  Exit code: {exit_code}")

    return out, err, exit_code


def upload_files(client):
    """Sube los archivos corregidos via SFTP."""
    sftp = client.open_sftp()
    print(f"\n📤 Subiendo archivos...")

    for local_path, remote_path in FILES_TO_UPLOAD:
        if not os.path.exists(local_path):
            print(f"  ⚠️ No encontrado: {local_path}")
            continue

        # Asegurar que el directorio remoto existe
        remote_dir = os.path.dirname(remote_path)
        try:
            sftp.stat(remote_dir)
        except FileNotFoundError:
            run_command(client, f"mkdir -p {remote_dir}")

        sftp.put(local_path, remote_path)
        print(f"  ✅ {local_path} -> {remote_path}")

    sftp.close()
    print("📤 Upload completo.")


def main():
    client = create_ssh_client()

    try:
        # 1. Verificar estado actual
        print("\n" + "=" * 50)
        print("📋 PASO 1: Verificar estado actual del servidor")
        print("=" * 50)

        run_command(client, f"cd {REMOTE_DIR} && git status || echo 'Not a git repo'")

        # 2. Verificar estructura de modelos
        print("\n" + "=" * 50)
        print("📋 PASO 2: Verificar estructura de modelos YuE")
        print("=" * 50)

        run_command(client, "ls -la /home/pepe/AI_MODELS/YuE/ 2>/dev/null || echo 'Models dir not found'")
        run_command(client, "ls -la /home/pepe/AI_MODELS/YuE/YuE-s1/ 2>/dev/null | head -5 || echo 'YuE-s1 not found'")
        run_command(client, "ls -la /home/pepe/AI_MODELS/YuE/YuE-s2/ 2>/dev/null | head -5 || echo 'YuE-s2 not found'")

        # 3. Subir archivos
        print("\n" + "=" * 50)
        print("📋 PASO 3: Subir archivos corregidos")
        print("=" * 50)

        upload_files(client)

        # 4. Verificar que los archivos se subieron correctamente
        print("\n" + "=" * 50)
        print("📋 PASO 4: Verificar archivos subidos")
        print("=" * 50)

        run_command(client, f"head -5 {REMOTE_DIR}/backend/main.py")
        run_command(client, f"wc -l {REMOTE_DIR}/backend/main.py")

        # 5. Reconstruir contenedor
        print("\n" + "=" * 50)
        print("📋 PASO 5: Reconstruir contenedor Docker")
        print("=" * 50)

        out, err, code = run_command(
            client,
            f"cd {REMOTE_DIR} && docker compose down && docker compose up -d --build",
            timeout=300
        )

        if code != 0:
            print("  ⚠️ Docker compose falló, intentando con docker-compose...")
            run_command(
                client,
                f"cd {REMOTE_DIR} && docker-compose down && docker-compose up -d --build",
                timeout=300
            )

        # 6. Esperar y verificar
        print("\n" + "=" * 50)
        print("📋 PASO 6: Esperando inicio del contenedor...")
        print("=" * 50)

        time.sleep(10)
        run_command(client, "docker ps --filter name=documusic")
        run_command(client, "docker logs documusic_backend --tail 20", timeout=30)

        # 7. Probar endpoint de diagnóstico
        print("\n" + "=" * 50)
        print("📋 PASO 7: Probando endpoint de diagnóstico")
        print("=" * 50)

        run_command(client, "curl -s http://localhost:8000/api/diagnostics | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8000/api/diagnostics")

        # 8. Probar estado general
        print("\n" + "=" * 50)
        print("📋 PASO 8: Estado del servidor")
        print("=" * 50)

        run_command(client, "curl -s http://localhost:8000/api | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8000/api")

        print("\n" + "=" * 50)
        print("✅ DESPLIEGUE COMPLETADO")
        print("=" * 50)
        print(f"🌐 Backend: http://{HOST}:8000/api")
        print(f"🔍 Diagnóstico: http://{HOST}:8000/api/diagnostics")

    except Exception as e:
        print(f"\n❌ Error durante el despliegue: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()
        print("\n🔗 Conexión cerrada.")


if __name__ == "__main__":
    main()
