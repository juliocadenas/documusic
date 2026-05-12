#!/usr/bin/env python3
"""Diagnose and fix NVIDIA driver crash on Madrid"""
import paramiko
import time

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)
print("Conectado!")

def run(cmd, timeout=30):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if out: print(f"  OUT: {out[:500]}")
    if err: print(f"  ERR: {err[:300]}")
    return out, err

# 1. Check if NVIDIA kernel module is loaded
run("lsmod | grep nvidia")

# 2. Check dmesg for GPU errors
run("sudo dmesg | grep -i 'nvidia\\|gpu\\|nvrm\\|pcie' | tail -20")

# 3. Check if driver is installed
run("dpkg -l | grep nvidia-driver")

# 4. Check kernel version
run("uname -r")

# 5. Try to reload the NVIDIA kernel module
run("sudo modprobe nvidia 2>&1")

# 6. Check if nvidia-smi works now
run("nvidia-smi 2>&1")

# 7. If still not working, check if we need to rebind the device
run("lspci | grep -i nvidia")

# 8. Check if the GPU is in D3 power state (powered off)
run("cat /sys/bus/pci/devices/0000:01:00.0/power/runtime_status 2>/dev/null || echo 'No power info'")

# 9. Try to rebind
run("echo 1 | sudo tee /sys/bus/pci/devices/0000:01:00.0/remove 2>/dev/null; echo 1 | sudo tee /sys/bus/pci/rescan 2>/dev/null; sleep 2; nvidia-smi 2>&1")

ssh.close()
print("\nDiagnóstico completo.")
