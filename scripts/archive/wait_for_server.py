#!/usr/bin/env python3
"""
Monitorear si el servidor vuelve a estar en línea después del reboot.
Cuando esté accesible, verificar el estado de la GPU.
"""
import paramiko
import time
import sys

HOST = "100.65.182.25"
USER = "pepe"
PASS = " "

def connect():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=10,
                look_for_keys=False, allow_agent=False)
    return ssh

def run(ssh, cmd, timeout=30):
    print(f"▸ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if out:
        for line in out.split("\n")[:15]:
            print(f"  {line}")
    if err and "[sudo]" not in err:
        for line in err.split("\n")[:3]:
            print(f"  ⚠ {line}")
    return out, err

print("🔍 Monitoreando servidor... (Ctrl+C para cancelar)")
print(f"   Host: {HOST}")
print(f"   Usuario: {USER}")

attempt = 0
max_attempts = 60  # 30 minutos total

while attempt < max_attempts:
    attempt += 1
    try:
        ssh = connect()
        print(f"\n✅ SERVIDOR EN LÍNEA! (intento {attempt})")

        print("\n" + "="*50)
        print("📋 VERIFICACIÓN POST-REBOOT")
        print("="*50)

        # Uptime
        run(ssh, "uptime")

        # GPU en PCIe?
        print("\n--- GPU en bus PCIe ---")
        lspci_out, _ = run(ssh, "lspci | grep -i nvidia")

        # nvidia-smi
        print("\n--- nvidia-smi ---")
        smi_out, smi_err = run(ssh, "nvidia-smi")

        if smi_out and "failed" not in (smi_out + smi_err).lower():
            print("\n🎉🎉🎉 ¡GPU FUNCIONANDO! 🎉🎉🎉")
        else:
            print("\n⚠️  nvidia-smi sigue fallando")
            # Diagnóstico adicional
            print("\n--- Diagnóstico adicional ---")
            run(ssh, "lspci -nn | grep -i 'nvidia\\|vga\\|3d'")
            run(ssh, "sudo dmesg | grep -i 'nvidia\\|NVRM\\|gpu' | tail -10")
            run(ssh, "lsmod | grep nvidia")
            run(ssh, "sudo modprobe nvidia 2>&1")
            time.sleep(2)
            run(ssh, "nvidia-smi 2>&1")

        # Docker
        print("\n--- Docker ---")
        run(ssh, "sudo systemctl start docker")
        run(ssh, "systemctl is-active docker")

        ssh.close()
        sys.exit(0)

    except Exception as e:
        if attempt % 10 == 0:
            print(f"  [{attempt}/{max_attempts}] {e} - {time.strftime('%H:%M:%S')}")
        time.sleep(30)

print(f"\n❌ Servidor no respondió después de {max_attempts * 30 / 60:.0f} minutos.")
print("El servidor probablemente está atascado en el prompt de LUKS.")
print("Necesita intervención física para ingresar la contraseña de LUKS.")
