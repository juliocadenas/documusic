#!/usr/bin/env python3
"""
Revive GPU on Madrid server (100.65.182.25)
Diagnóstico completo y reparación del driver NVIDIA.
Contraseña: en blanco (vacía) - usa SSH key o look_for_keys
"""
import paramiko
import time
import sys
import os

HOST = "100.65.182.25"
USER = "pepe"
PASS = ""  # Contraseña en blanco

def connect():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        # Intentar primero con SSH key (look_for_keys=True por defecto)
        ssh.connect(HOST, username=USER, password=None, timeout=15,
                    look_for_keys=True, allow_agent=True)
        print("✅ Conectado al servidor via SSH key!")
        return ssh
    except Exception as e1:
        print(f"  SSH key falló: {e1}")
        try:
            # Intentar con contraseña vacía usando allow_agent
            ssh.connect(HOST, username=USER, password=" ", timeout=15,
                        look_for_keys=False, allow_agent=False)
            print("✅ Conectado al servidor con password blank!")
            return ssh
        except Exception as e2:
            print(f"  Password blank falló: {e2}")
            try:
                # Último intento: usar pexpect/subprocess para ssh directo
                print("  Intentando conexión alternativa...")
                ssh.connect(HOST, username=USER, timeout=15,
                            look_for_keys=True, allow_agent=True,
                            key_filename=os.path.expanduser("~/.ssh/id_rsa"))
                print("✅ Conectado via id_rsa!")
                return ssh
            except Exception as e3:
                print(f"❌ Todas las conexiones fallaron:")
                print(f"  1. SSH key: {e1}")
                print(f"  2. Password blank: {e2}")
                print(f"  3. id_rsa: {e3}")
                print("\n  Solución: Genera una clave SSH y cópiala al servidor:")
                print("    ssh-keygen -t rsa -N '' -f ~/.ssh/id_rsa")
                print("    ssh-copy-id pepe@100.65.182.25")
                sys.exit(1)

def run(ssh, cmd, sudo=False, timeout=30, verbose=True):
    """Ejecutar comando remoto. Si sudo=True, antepone sudo."""
    if sudo:
        full_cmd = f"sudo {cmd}"
    else:
        full_cmd = cmd

    if verbose:
        print(f"\n{'🔧' if sudo else '▸'} {full_cmd}")

    try:
        stdin, stdout, stderr = ssh.exec_command(full_cmd, timeout=timeout)
        # Si es sudo con contraseña vacía, enviar enter
        if sudo and PASS == "":
            time.sleep(0.5)
            try:
                stdin.write("\n")
                stdin.flush()
            except:
                pass

        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        if verbose:
            if out:
                for line in out.split("\n")[:15]:
                    print(f"  {line}")
                if len(out.split("\n")) > 15:
                    print(f"  ... ({len(out.split(chr(10)))} líneas total)")
            if err and "[sudo]" not in err:
                for line in err.split("\n")[:5]:
                    print(f"  ⚠ {line}")
        return out, err
    except Exception as e:
        if verbose:
            print(f"  ❌ Error: {e}")
        return "", str(e)

def diagnose(ssh):
    """Fase 1: Diagnóstico completo"""
    print("\n" + "="*60)
    print("🔍 FASE 1: DIAGNÓSTICO")
    print("="*60)

    results = {}

    # 1. Kernel
    out, _ = run(ssh, "uname -r")
    results['kernel'] = out

    # 2. ¿GPU visible en PCIe?
    out, _ = run(ssh, "lspci | grep -i 'nvidia\\|vga\\|3d\\|display'")
    results['pcie'] = out

    # 3. ¿Módulo NVIDIA cargado?
    out, _ = run(ssh, "lsmod | grep nvidia")
    results['lsmod'] = out

    # 4. nvidia-smi
    out, err = run(ssh, "nvidia-smi")
    results['nvidia_smi'] = out
    results['nvidia_smi_err'] = err

    # 5. Driver instalado
    out, _ = run(ssh, "dpkg -l | grep nvidia-driver")
    results['driver_pkg'] = out

    # 6. Errores en dmesg
    out, _ = run(ssh, "sudo dmesg | grep -i 'nvidia\\|gpu\\|nvrm\\|pcie\\|NVRM' | tail -30", sudo=True)
    results['dmesg'] = out

    # 7. Power state
    out, _ = run(ssh, "cat /sys/bus/pci/devices/0000:01:00.0/power/runtime_status 2>/dev/null || echo 'not_found'")
    results['power'] = out

    # 8. Driver bind status
    out, _ = run(ssh, "lspci -k | grep -A3 'NVIDIA\\|VGA'")
    results['driver_bind'] = out

    # 9. Secure Boot status
    out, _ = run(ssh, "mokutil --sb-state 2>/dev/null || echo 'unknown'")
    results['secure_boot'] = out

    # 10. DKMS status
    out, _ = run(ssh, "dkms status 2>/dev/null | grep nvidia")
    results['dkms'] = out

    # 11. Kernel modules on disk
    out, _ = run(ssh, f"find /lib/modules/$(uname -r) -name 'nvidia*.ko*' 2>/dev/null | head -10")
    results['modules_on_disk'] = out

    # 12. Docker status
    out, _ = run(ssh, "systemctl is-active docker")
    results['docker'] = out

    return results

def analyze(results):
    """Analizar resultados del diagnóstico"""
    print("\n" + "="*60)
    print("📊 FASE 2: ANÁLISIS")
    print("="*60)

    issues = []

    # GPU visible en PCIe?
    if not results['pcie']:
        issues.append("CRITICAL: GPU no detectada en bus PCIe")
        print("  🔴 GPU NO visible en lspci - posible problema hardware")
    else:
        print(f"  🟢 GPU visible en PCIe: {results['pcie'][:80]}")

    # Módulo cargado?
    if not results['lsmod']:
        issues.append("MODULE_NOT_LOADED: Módulos NVIDIA no cargados")
        print("  🔴 Módulos NVIDIA NO cargados en kernel")
    else:
        print(f"  🟢 Módulos NVIDIA cargados")

    # Driver instalado?
    if not results['driver_pkg']:
        issues.append("NO_DRIVER: No hay paquete nvidia-driver instalado")
        print("  🔴 No hay paquete nvidia-driver instalado")
    else:
        print(f"  🟢 Driver instalado: {results['driver_pkg'][:80]}")

    # Módulos en disco?
    if not results['modules_on_disk']:
        issues.append("NO_MODULES: No hay módulos .ko para este kernel")
        print("  🔴 No hay módulos NVIDIA compilados para este kernel")
    else:
        print(f"  🟢 Módulos en disco encontrados")

    # DKMS OK?
    if results['dkms']:
        print(f"  ℹ️  DKMS: {results['dkms'][:80]}")
    else:
        print("  ⚠️  DKMS no reporta módulos NVIDIA")

    # dmesg errors
    if 'NVRM' in results.get('dmesg', '') or 'GPU' in results.get('dmesg', ''):
        print(f"  ⚠️  Errores en dmesg detectados")
        issues.append("DMESG_ERRORS: Errores relacionados con GPU en dmesg")

    # Secure Boot
    if 'enabled' in results.get('secure_boot', '').lower():
        issues.append("SECURE_BOOT: Secure Boot habilitado puede bloquear módulos")
        print("  🔴 Secure Boot HABILITADO - puede bloquear drivers")
    else:
        print(f"  🟢 Secure Boot: {results['secure_boot']}")

    return issues

def fix_step1_reload_modules(ssh):
    """Intento 1: Recargar módulos del kernel"""
    print("\n" + "="*60)
    print("🔧 INTENTO 1: Recargar módulos NVIDIA")
    print("="*60)

    # Detener Docker para liberar GPU
    run(ssh, "systemctl stop docker", sudo=True)
    time.sleep(2)

    # Descargar módulos
    run(ssh, "modprobe -r nvidia_uvm nvidia_drm nvidia_modeset nvidia", sudo=True)
    time.sleep(2)

    # Cargar módulos
    out, err = run(ssh, "modprobe nvidia", sudo=True)
    if err and "not found" in err:
        print("  ❌ Módulo nvidia no encontrado - saltando al siguiente intento")
        return False

    run(ssh, "modprobe nvidia_uvm", sudo=True)
    run(ssh, "modprobe nvidia_drm", sudo=True)
    run(ssh, "modprobe nvidia_modeset", sudo=True)
    time.sleep(2)

    # Verificar
    out, err = run(ssh, "nvidia-smi")
    if "failed" not in (out + err).lower():
        print("\n  ✅ ¡nvidia-smi funciona después de recargar módulos!")
        run(ssh, "systemctl start docker", sudo=True)
        return True
    else:
        print("  ❌ No funcionó recargar módulos")
        return False

def fix_step2_pcie_rescan(ssh):
    """Intento 2: Rescan PCIe + recargar"""
    print("\n" + "="*60)
    print("🔧 INTENTO 2: PCIe Rescan")
    print("="*60)

    # Descargar módulos
    run(ssh, "modprobe -r nvidia_uvm nvidia_drm nvidia_modeset nvidia", sudo=True)
    time.sleep(2)

    # Encontrar dirección PCIe de la GPU
    out, _ = run(ssh, "lspci -D | grep -i nvidia | head -1 | awk '{print $1}'")
    gpu_addr = out.strip()

    if gpu_addr:
        print(f"  GPU en dirección: {gpu_addr}")
        # Remover dispositivo
        run(ssh, f"echo 1 > /sys/bus/pci/devices/{gpu_addr}/remove", sudo=True)
    else:
        # Intentar dirección común
        run(ssh, "echo 1 > /sys/bus/pci/devices/0000:01:00.0/remove", sudo=True)

    time.sleep(2)

    # Rescan
    print("  Rescaneando bus PCIe...")
    run(ssh, "echo 1 > /sys/bus/pci/rescan", sudo=True)
    time.sleep(3)

    # Verificar GPU visible
    out, _ = run(ssh, "lspci | grep -i nvidia")
    if not out:
        print("  ❌ GPU sigue sin aparecer después de rescan")
        return False

    print(f"  🟢 GPU visible: {out}")

    # Recargar módulos
    run(ssh, "modprobe nvidia", sudo=True)
    run(ssh, "modprobe nvidia_uvm", sudo=True)
    run(ssh, "modprobe nvidia_drm", sudo=True)
    run(ssh, "modprobe nvidia_modeset", sudo=True)
    time.sleep(2)

    # Verificar
    out, err = run(ssh, "nvidia-smi")
    if "failed" not in (out + err).lower():
        print("\n  ✅ ¡nvidia-smi funciona después de PCIe rescan!")
        run(ssh, "systemctl start docker", sudo=True)
        return True
    else:
        print("  ❌ No funcionó PCIe rescan")
        return False

def fix_step3_rebuild_modules(ssh):
    """Intento 3: Recompilar módulos con DKMS"""
    print("\n" + "="*60)
    print("🔧 INTENTO 3: Recompilar módulos NVIDIA (DKMS)")
    print("="*60)

    # Ver qué versión de driver tenemos
    out, _ = run(ssh, "dpkg -l | grep nvidia-driver | head -1")
    if out:
        # Extraer versión
        parts = out.split()
        version = ""
        for p in parts:
            if p.startswith("5") or p.startswith("4"):
                version = p
                break
        if version:
            print(f"  Versión driver: {version}")

    # DKMS autoinstall
    run(ssh, "dkms autoinstall", sudo=True, timeout=120)
    time.sleep(2)

    # Cargar módulos
    run(ssh, "modprobe nvidia", sudo=True)
    run(ssh, "modprobe nvidia_uvm", sudo=True)
    run(ssh, "modprobe nvidia_drm", sudo=True)
    run(ssh, "modprobe nvidia_modeset", sudo=True)
    time.sleep(2)

    out, err = run(ssh, "nvidia-smi")
    if "failed" not in (out + err).lower():
        print("\n  ✅ ¡nvidia-smi funciona después de recompilar!")
        run(ssh, "systemctl start docker", sudo=True)
        return True
    else:
        print("  ❌ No funcionó recompilar")
        return False

def fix_step4_reinstall_driver(ssh):
    """Intento 4: Reinstalar driver NVIDIA"""
    print("\n" + "="*60)
    print("🔧 INTENTO 4: Reinstalar driver NVIDIA")
    print("="*60)

    # Detectar qué driver instalar según la GPU
    out, _ = run(ssh, "lspci | grep -i nvidia")
    print(f"  GPU: {out}")

    # En Pop!_OS, usar system76-power o apt
    run(ssh, "apt update", sudo=True, timeout=120)

    # Reinstalar el driver
    run(ssh, "apt install --reinstall nvidia-driver-550 -y 2>/dev/null || apt install --reinstall nvidia-driver-535 -y 2>/dev/null || apt install --reinstall nvidia-driver -y", sudo=True, timeout=300)

    time.sleep(2)

    # Cargar módulos
    run(ssh, "modprobe nvidia", sudo=True)
    run(ssh, "modprobe nvidia_uvm", sudo=True)
    run(ssh, "modprobe nvidia_drm", sudo=True)
    run(ssh, "modprobe nvidia_modeset", sudo=True)
    time.sleep(2)

    out, err = run(ssh, "nvidia-smi")
    if "failed" not in (out + err).lower():
        print("\n  ✅ ¡nvidia-smi funciona después de reinstalar!")
        run(ssh, "systemctl start docker", sudo=True)
        return True
    else:
        print("  ❌ No funcionó reinstalar driver")
        return False

def main():
    ssh = connect()

    # FASE 1: Diagnóstico
    results = diagnose(ssh)

    # FASE 2: Análisis
    issues = analyze(results)

    if not issues:
        print("\n✅ No se detectaron problemas. nvidia-smi debería funcionar.")
        out, _ = run(ssh, "nvidia-smi")
        if out:
            print(out)
        ssh.close()
        return

    print(f"\n  Problemas detectados: {len(issues)}")
    for i, issue in enumerate(issues, 1):
        print(f"    {i}. {issue}")

    # FASE 3: Intentar reparaciones en orden
    fixed = False

    # Si no hay módulos en disco, necesitamos recompilar/reinstalar
    has_modules = bool(results.get('modules_on_disk'))
    has_driver_pkg = bool(results.get('driver_pkg'))
    gpu_visible = bool(results.get('pcie'))

    if not gpu_visible:
        print("\n  ⚠️  GPU no visible en PCIe. Intentando rescan primero...")
        fixed = fix_step2_pcie_rescan(ssh)

    if not fixed and has_modules and has_driver_pkg:
        fixed = fix_step1_reload_modules(ssh)

    if not fixed and gpu_visible:
        fixed = fix_step2_pcie_rescan(ssh)

    if not fixed and has_driver_pkg:
        fixed = fix_step3_rebuild_modules(ssh)

    if not fixed:
        fixed = fix_step4_reinstall_driver(ssh)

    # Resultado final
    print("\n" + "="*60)
    print("📋 RESULTADO FINAL")
    print("="*60)

    out, err = run(ssh, "nvidia-smi")
    if out and "failed" not in (out + err).lower():
        print("\n🎉 ¡GPU REVIVIDA CON ÉXITO!")
        print(out)
    else:
        print("\n💀 No se pudo revivir la GPU automáticamente.")
        print("Posibles causas:")
        print("  1. Hardware desconectado físicamente")
        print("  2. Secure Boot bloqueando módulos")
        print("  3. Kernel incompatible con el driver")
        print("  4. GPU en estado de error irre recuperable (GSP firmware)")
        print("\nRecomendación: reiniciar el servidor con 'sudo reboot'")
        print("Si después del reboot sigue fallando, puede ser problema de hardware.")

    # Asegurar que Docker esté corriendo
    run(ssh, "systemctl start docker", sudo=True)
    run(ssh, "systemctl is-active docker")

    ssh.close()
    print("\nDesconectado.")

if __name__ == "__main__":
    main()
