import paramiko
import time

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

def run(cmd):
    print(f"> {cmd}")
    stdin, stdout, stderr = client.exec_command(f"echo {PASS} | sudo -S bash -c '{cmd}'")
    print(stdout.read().decode('utf-8'))
    print(stderr.read().decode('utf-8'))

# Stop services
run("systemctl stop docker")
# Unload drivers
run("modprobe -r nvidia_uvm nvidia_drm nvidia_modeset nvidia")
time.sleep(2)

# Remove device from PCIe bus
print("Eliminando GPU del bus PCIe...")
run("echo 1 > /sys/bus/pci/devices/0000:01:00.0/remove")
time.sleep(2)

# Rescan PCIe bus to wake up hardware
print("Escanenado bus PCIe...")
run("echo 1 > /sys/bus/pci/rescan")
time.sleep(3)

# Reload drivers
run("modprobe nvidia")
run("modprobe nvidia_uvm")
run("modprobe nvidia_drm")
run("modprobe nvidia_modeset")
time.sleep(2)

# Check status
run("nvidia-smi")
run("systemctl start docker")

client.close()
