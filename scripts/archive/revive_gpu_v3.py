#!/usr/bin/env python3
"""
Revive GPU v3 - Diagnóstico profundo + PCIe rescan + reboot automático
Sin interacción requerida.
"""
import paramiko
import time
import sys

HOST = "100.65.182.25"
USER = "pepe"
PASS = " "  # Contraseña en blanco

def connect():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=15,
                look_for_keys=False, allow_agent=False)
    return ssh

def run(ssh, cmd, timeout=30, verbose=True):
    if verbose:
        print(f"\n▸ {cmd}")
    try:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        if verbose and out:
            for line in out.split("\n")[:20]:
                print(f"  {line}")
        if verbose and err and "[sudo]" not in err:
            for line in err.split("\n")[:3]:
                print(f"  ⚠ {line}")
        return out, err
    except Exception as e:
        if verbose:
            print(f"  ❌ {e}")
        return "", str(e)

def run_sudo(ssh, cmd, timeout=30):
    """Ejecutar con sudo bash -c para que las redirecciones funcionen"""
    # Escapar comillas simples en el comando
    escaped = cmd.replace("'", "'\\''")
    return run(ssh, f"sudo bash -c '{escaped}'", timeout=timeout)

def main():
    print("🔌 Conectando...")
    ssh = connect()
    print("✅ Conectado!")

    # ============================================================
    # FASE 1: Diagnóstico profundo
    # ============================================================
    print("\n" + "="*60)
    print("🔍 FASE 1: DIAGNÓSTICO PROFUNDO")
    print("="*60)

    # 1. Todas las GPUs/Display devices
    print("\n--- Dispositivos de video ---")
    run(ssh, "lspci -nn | grep -E ':0[23]00|:0302|VGA|3D|Display'")

    # 2. Buscar NVIDIA específicamente
    print("\n--- Buscando NVIDIA ---")
    nvidia_lspci, _ = run(ssh, "lspci -D -nn | grep -i nvidia")

    # 3. Buscar vendor 10de (NVIDIA) en sysfs
    print("\n--- Buscando vendor 10de en sysfs ---")
    nvidia_sysfs, _ = run(ssh, "for d in /sys/bus/pci/devices/*/vendor; do val=$(cat $d 2>/dev/null); if [ \"$val\" = '0x10de' ]; then echo \"NVIDIA: $(dirname $d)\"; fi; done; echo '--- fin busqueda ---'")

    # 4. Topología PCIe
    print("\n--- Topología PCIe ---")
    run(ssh, "lspci -t")

    # 5. Todos los dispositivos en el bus
    print("\n--- Todos los dispositivos PCI ---")
    run(ssh, "lspci -nn | head -30")

    # 6. Dispositivos en /sys/bus/pci/devices/
    print("\n--- Dispositivos en sysfs ---")
    run(ssh, "ls /sys/bus/pci/devices/ | sort")

    # 7. dmesg errores recientes
    print("\n--- Errores NVRM recientes ---")
    run(ssh, "sudo dmesg | grep -i 'NVRM\\|nvidia.*error\\|gpu.*error' | tail -15")

    # 8. ASPM (Active State Power Management) - puede apagar el link PCIe
    print("\n--- PCIe ASPM policy ---")
    run(ssh, "cat /sys/module/pcie_aspm/parameters/policy 2>/dev/null || echo 'no aspm info'")

    # 9. Ver si hay un dispositivo en 01:00
    print("\n--- Dispositivos en 0000:01:00.x ---")
    run(ssh, "ls -la /sys/bus/pci/devices/0000:01:00.0/power/ 2>/dev/null || echo 'No existe 0000:01:00.0'")

    # 10. Ver config space de posible dirección NVIDIA
    print("\n--- PCI config space 01:00.0 ---")
    run(ssh, "sudo lspci -vvv -s 01:00.0 2>/dev/null | head -20 || echo 'No hay dispositivo en 01:00.0'")

    # 11. Ver acpi power state de todos los dispositivos
    print("\n--- Power states de dispositivos PCI ---")
    run(ssh, "for d in /sys/bus/pci/devices/*/power/runtime_status; do echo \"$(dirname $d | xargs basename): $(cat $d)\"; done")

    # 12. Kernel version
    print("\n--- Kernel ---")
    run(ssh, "uname -r")

    # 13. Secure Boot
    print("\n--- Secure Boot ---")
    run(ssh, "mokutil --sb-state 2>/dev/null; cat /sys/kernel/security/securelevel 2>/dev/null; echo '---'")

    # ============================================================
    # FASE 2: Intentar revivir sin reboot
    # ============================================================
    print("\n" + "="*60)
    print("🔧 FASE 2: INTENTAR REVIVIR SIN REBOOT")
    print("="*60)

    gpu_found = bool(nvidia_lspci) or '10de' in nvidia_sysfs

    if not gpu_found:
        print("\n  GPU NVIDIA NO detectada en bus PCIe. Intentando rescan...")

        # Detener Docker
        run_sudo(ssh, "systemctl stop docker")
        time.sleep(2)

        # Descargar módulos
        run_sudo(ssh, "modprobe -r nvidia_uvm nvidia_drm nvidia_modeset nvidia 2>/dev/null; echo 'modules unloaded'")
        time.sleep(1)

        # Intento A: Rescan simple
        print("\n  --- Intento A: Rescan simple ---")
        run_sudo(ssh, "echo 1 > /sys/bus/pci/rescan")
        time.sleep(5)

        nvidia_check, _ = run(ssh, "lspci | grep -i nvidia")
        if nvidia_check:
            print(f"  🟢 GPU apareció: {nvidia_check}")
            gpu_found = True
        else:
            print("  ❌ Rescan simple no funcionó")

        # Intento B: Remover todos los dispositivos debajo del root port y rescan
        if not gpu_found:
            print("\n  --- Intento B: Remover root port + rescan ---")
            # Buscar el root port que alimenta el slot PCIe x16
            # Normalmente es 00:01.0 o 00:01.1 en plataformas Intel Alder Lake
            run(ssh, "lspci -t")  # Ya lo mostramos, pero para referencia

            # Buscar root ports
            root_ports, _ = run(ssh, "lspci -D -nn | grep -i 'root port\\|pci bridge' | head -10", verbose=False)
            print(f"  Root ports encontrados:\n{root_ports}")

            # Intentar remover y rescan cada bridge que pueda tener la GPU debajo
            for line in root_ports.split("\n"):
                if not line.strip():
                    continue
                addr = line.split()[0]
                print(f"  Probando bridge {addr}...")

                # Poner el bridge en D0 (activo)
                run_sudo(ssh, f"echo on > /sys/bus/pci/devices/{addr}/power/control 2>/dev/null")
                time.sleep(0.5)

            # Rescan agresivo
            run_sudo(ssh, "echo 1 > /sys/bus/pci/rescan")
            time.sleep(5)

            nvidia_check, _ = run(ssh, "lspci | grep -i nvidia")
            if nvidia_check:
                print(f"  🟢 GPU apareció: {nvidia_check}")
                gpu_found = True
            else:
                print("  ❌ Bridge power + rescan no funcionó")

        # Intento C: Forzar power on de todos los dispositivos + rescan
        if not gpu_found:
            print("\n  --- Intento C: Power on todos + rescan ---")
            run_sudo(ssh, "for d in /sys/bus/pci/devices/*/power/control; do echo on > $d 2>/dev/null; done; echo 'all powered on'")
            time.sleep(2)
            run_sudo(ssh, "echo 1 > /sys/bus/pci/rescan")
            time.sleep(5)

            nvidia_check, _ = run(ssh, "lspci | grep -i nvidia")
            if nvidia_check:
                print(f"  🟢 GPU apareció: {nvidia_check}")
                gpu_found = True
            else:
                print("  ❌ Power on + rescan no funcionó")

    # Si la GPU fue encontrada, cargar drivers
    if gpu_found:
        print("\n  Cargando drivers NVIDIA...")
        run_sudo(ssh, "modprobe nvidia")
        run_sudo(ssh, "modprobe nvidia_uvm")
        run_sudo(ssh, "modprobe nvidia_drm")
        run_sudo(ssh, "modprobe nvidia_modeset")
        time.sleep(3)

        out, err = run(ssh, "nvidia-smi")
        if out and "failed" not in (out + err).lower():
            print("\n🎉 ¡GPU REVIVIDA SIN REBOOT!")
            print(out)
            run_sudo(ssh, "systemctl start docker")
            ssh.close()
            return

    # ============================================================
    # FASE 3: Reboot
    # ============================================================
    print("\n" + "="*60)
    print("⚡ FASE 3: REBOOT NECESARIO")
    print("="*60)

    print("""
  La GPU NVIDIA no pudo ser detectada por software.
  El bus PCIe no la ve después de múltiples intentos de rescan.
  
  Esto típicamente significa:
  1. La GPU está en estado D3cold (apagada por ACPI)
  2. El firmware/BIOS necesita re-inicializar el enlace PCIe
  3. Un reboot del sistema lo resolverá

  Ejecutando reboot en 5 segundos...
    """)

    time.sleep(5)

    # Reboot!
    print("  🔄 Reiniciando servidor...")
    run_sudo(ssh, "reboot", timeout=10)
    ssh.close()

    # Esperar a que el servidor vuelva
    print("  ⏳ Esperando 90 segundos para que el servidor reinicie...")
    time.sleep(90)

    # Reconectar y verificar
    print("\n  🔌 Reconectando...")
    for attempt in range(10):
        try:
            ssh = connect()
            print(f"  ✅ Reconectado (intento {attempt+1})!")

            print("\n" + "="*60)
            print("📋 VERIFICACIÓN POST-REBOOT")
            print("="*60)

            # Verificar GPU
            run(ssh, "lspci | grep -i nvidia")
            out, err = run(ssh, "nvidia-smi")

            if out and "failed" not in (out + err).lower():
                print("\n🎉🎉🎉 ¡GPU REVIVIDA DESPUÉS DEL REBOOT! 🎉🎉🎉")
                print(out)
            else:
                print("\n💀 La GPU sigue sin funcionar después del reboot.")
                print("\n  Diagnóstico adicional:")
                run(ssh, "lspci -nn | grep -i nvidia")
                run(ssh, "sudo dmesg | grep -i 'nvidia\\|NVRM\\|gpu' | tail -20")
                run(ssh, "ls /sys/bus/pci/devices/ | sort")
                print("\n  ⚠️  Si después de un reboot la GPU no aparece en lspci,")
                print("  el problema es probablemente de HARDWARE:")
                print("  - GPU físicamente desconectada o dañada")
                print("  - Slot PCIe dañado")
                print("  - Problema de alimentación eléctrica")
                print("  - BIOS/UEFI configurado para deshabilitar la GPU discreta")

            # Restaurar Docker
            run_sudo(ssh, "systemctl start docker")
            run(ssh, "systemctl is-active docker")

            ssh.close()
            return

        except Exception as e:
            print(f"  Intento {attempt+1}/10: {e}")
            time.sleep(15)

    print("\n❌ No se pudo reconectar al servidor después del reboot.")
    print("  Intenta conectarte manualmente: ssh pepe@100.65.182.25")

if __name__ == "__main__":
    main()
