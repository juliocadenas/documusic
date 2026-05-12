import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

def run(cmd):
    client.exec_command(f"echo {PASS} | sudo -S bash -c '{cmd}'")

print("Modificando el límite del Watchdog...")
FIX_SCRIPT = """
with open('/opt/gpu_watchdog.py', 'r') as f:
    code = f.read()

code = code.replace('VRAM_LIMIT_MB = 15300', 'VRAM_LIMIT_MB = 16000')

with open('/opt/gpu_watchdog.py', 'w') as f:
    f.write(code)
"""
client.exec_command(f"cat << 'EOF' > /tmp/update_watchdog.py\n{FIX_SCRIPT}\nEOF")
run("python3 /tmp/update_watchdog.py")
run("systemctl restart gpu_watchdog")

print("Listo!")
client.close()
