#!/usr/bin/env python3
"""
Revive GPU v2 - PCIe Rescan con permisos correctos + reboot si es necesario
El problema: la GPU NVIDIA no aparece en lspci (solo Intel Iris Xe)
Solución: forzar rescan PCIe con permisos correctos, o reboot
"""
import paramiko
import time
import sys

HOST = "100.65.182.25"
USER = "pepe"
PASS = " "  # Contraseña en blanco - paramiko necesita al menos 1 char

def connect():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=15,
                look_for_keys=False, allow_agent=False)
    print("✅ Conectado!")
    return ssh

def run(ssh, cmd, timeout=30):
    """Ejecutar comando con sudo correctamente"""
    print(f"\n▸ {cmd}")
    try:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        if out:
            for line in out.split("\n")[:20]:
                print(f"  {line}")
            if len(out.split("\n")) > 20:
                print(f"  ... ({len(out.split(chr(10)))} líneas)")
        if err and "[sudo]" not in err:
            for line in err.split("\n")[:5]:
                print(f"  ⚠ {line}")
        return out, err
    except Exception as e:
        print(f"  ❌ {e}")
        return "", str(e)

def run_sudo(ssh, cmd, timeout=30):
    """Ejecutar con sudo usando -S para stdin y bash -c para redirecciones"""
    # Usamos sudo bash -c 'comando' para que las redirecciones funcionen con permisos root
    full_cmd = f"sudo bash -c '{cmd}'"
    return run(ssh, full_cmd, timeout=timeout)

def main():
    ssh = connect()

    print("\n" + "="*60)
    print("🔍 DIAGNÓSTICO INICIAL")
    print("="*60)

    # 1. Ver todas las GPUs
    run(ssh, "lspci -nn | grep -i 'vga\\|3d\\|display\\|nvidia'")

    # 2. Buscar dispositivos NVIDIA en cualquier lugar del bus PCIe
    run(ssh, "lspci -D | grep -i nvidia")

    # 3. Ver todos los dispositivos PCI de clase display/3D/VGA
    run(ssh, "lspci -D -nn | grep -E ':0[23]00|:0302'")

    # 4. Listar todos los dispositivos PCI (resumido) para ver si hay algo en 01:00
    run(ssh, "lspci | head -20")

    # 5. Ver power state de la dirección 01:00.0
    run(ssh, "ls -la /sys/bus/pci/devices/0000:01:00.0/ 2>/dev/null || echo 'No existe 0000:01:00.0'")

    # 6. Ver todos los dispositivos en /sys/bus/pci/devices/
    run(ssh, "ls /sys/bus/pci/devices/ | sort")

    # 7. Ver si hay algún dispositivo NVIDIA en /sys
    run(ssh, "find /sys/bus/pci/devices/ -name '*nvidia*' 2>/dev/null || echo 'No hay dispositivos nvidia en sysfs'")

    # 8. Ver el vendor de cada dispositivo PCI para buscar NVIDIA (vendor 10de)
    run(ssh, "for d in /sys/bus/pci/devices/*/vendor; do val=$(cat $d 2>/dev/null); if [ \"$val\" = '0x10de' ]; then echo \"ENCONTRADO NVIDIA: $d\"; fi; done; echo 'Búsqueda completada'")

    print("\n" + "="*60)
    print("🔧 INTENTO 1: Forzar PCIe Rescan (con permisos correctos)")
    print("="*60)

    # Detener Docker
    run_sudo(ssh, "systemctl stop docker")
    time.sleep(2)

    # Descargar módulos NVIDIA
    run_sudo(ssh, "modprobe -r nvidia_uvm nvidia_drm nvidia_modeset nvidia 2>/dev/null; echo done")
    time.sleep(1)

    # Forzar rescan del bus PCIe - usando sudo bash -c para permisos correctos
    print("\n  Forzando rescan PCIe...")
    run_sudo(ssh, "echo 1 > /sys/bus/pci/rescan")
    time.sleep(5)

    # Verificar si la GPU apareció
    print("\n  Verificando si la GPU apareció...")
    out, _ = run(ssh, "lspci | grep -i nvidia")

    if out:
        print(f"\n  🟢 ¡GPU NVIDIA detectada después del rescan: {out}")
        # Cargar módulos
        run_sudo(ssh, "modprobe nvidia")
        run_sudo(ssh, "modprobe nvidia_uvm")
        run_sudo(ssh, "modprobe nvidia_drm")
        run_sudo(ssh, "modprobe nvidia_modeset")
        time.sleep(3)

        # Verificar nvidia-smi
        out, err = run(ssh, "nvidia-smi")
        if out and "failed" not in (out + err).lower():
            print("\n🎉 ¡GPU REVIVIDA SIN REBOOT!")
            run_sudo(ssh, "systemctl start docker")
            ssh.close()
            return
    else:
        print("\n  ❌ GPU sigue sin aparecer")

    print("\n" + "="*60)
    print("🔧 INTENTO 2: Remover y re-agregar dispositivo PCIe")
    print("="*60)

    # Buscar si hay algún dispositivo en 01:00.x
    out, _ = run(ssh, "ls /sys/bus/pci/devices/ | grep '0000:01:00'")

    if out:
        for dev in out.split("\n"):
            dev = dev.strip()
            if dev:
                print(f"  Removiendo {dev}...")
                run_sudo(ssh, f"echo 1 > /sys/bus/pci/devices/{dev}/remove")
                time.sleep(1)
    else:
        print("  No hay dispositivos en 0000:01:00.x")

    # También remover la Intel VGA para forzar un refresh completo
    # (no, mejor no tocar la Intel)

    # Rescan
    print("\n  Rescaneando bus PCIe completo...")
    run_sudo(ssh, "echo 1 > /sys/bus/pci/rescan")
    time.sleep(5)

    # Verificar
    out, _ = run(ssh, "lspci | grep -i nvidia")
    if out:
        print(f"\n  🟢 ¡GPU NVIDIA detectada: {out}")
        run_sudo(ssh, "modprobe nvidia nvidia_uvm nvidia_drm nvidia_modeset")
        time.sleep(3)
        out, err = run(ssh, "nvidia-smi")
        if out and "failed" not in (out + err).lower():
            print("\n🎉 ¡GPU REVIVIDA!")
            run_sudo(ssh, "systemctl start docker")
            ssh.close()
            return
    else:
        print("\n  ❌ GPU sigue sin aparecer")

    print("\n" + "="*60)
    print("🔧 INTENTO 3: Buscar GPU en otros buses PCIe")
    print("="*60)

    # Listar TODOS los dispositivos PCI con sus vendors
    run(ssh, "lspci -nn | head -30")

    # Buscar vendor NVIDIA (10de) en cualquier lugar
    run(ssh, "grep -r '10de' /sys/bus/pci/devices/*/vendor 2>/dev/null || echo 'No se encontró vendor 10de (NVIDIA)'")

    # Ver la topología PCIe completa
    run(ssh, "lspci -t")

    # Ver si hay un dispositivo 3D controller que podría ser la NVIDIA
    run(ssh, "lspci -nn | grep -E '0300|0302|0380'")

    print("\n" + "="*60)
    print("🔧 INTENTO 4: Reboot del servidor")
    print("="*60)

    print("""
  La GPU NVIDIA no aparece en el bus PCIe después de:
  - modprobe -r + modprobe
  - PCIe rescan
  - DKMS recompilación
  - Reinstalación del driver

  Esto indica que la GPU está en un estado de energía bajo (D3cold)
  o necesita un reinicio del firmware/BIOS para ser detectada.

  ⚡ SOLUCIÓN: Reboot del servidor
    """)

    answer = input("  ¿Quieres reiniciar el servidor ahora? (s/n): ").strip().lower()

    if answer == 's':
        print("\n  Reiniciando servidor...")
        run_sudo(ssh, "reboot")
        print("  Servidor reiniciándose. Esperando 60 segundos...")
        ssh.close()
        time.sleep(60)

        # Reconectar y verificar
        print("\n  Reconectando...")
        for attempt in range(5):
            try:
                ssh = connect()
                print("  ✅ Servidor de vuelta!")
                out, err = run(ssh, "nvidia-smi")
                if out and "failed" not in (out + err).lower():
                    print("\n🎉 ¡GPU REVIVIDA DESPUÉS DEL REBOOT!")
                    print(out)
                else:
                    print("\n💀 La GPU sigue sin funcionar después del reboot.")
                    print("  Esto puede ser un problema de hardware.")
                    print("  Verificar:")
                    run(ssh, "lspci | grep -i nvidia")
                    run(ssh, "sudo dmesg | grep -i 'nvidia\\|NVRM' | tail -10")
                run_sudo(ssh, "systemctl start docker")
                ssh.close()
                return
            except:
                print(f"  Intento {attempt+1}/5 fallido, esperando...")
                time.sleep(15)
    else:
        print("\n  No se reinició. Puedes reiniciar manualmente con:")
        print("    ssh pepe@100.65.182.25 'sudo reboot'")
        run_sudo(ssh, "systemctl start docker")

    ssh.close()

if __name__ == "__main__":
    main()
