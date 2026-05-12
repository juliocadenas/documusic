import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')
HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(f"echo {PASS} | sudo -S bash -c '{cmd}'")
    err = stderr.read().decode('utf-8')
    out = stdout.read().decode('utf-8')
    if err: print("ERR:", err)
    if out: print("OUT:", out)

print("1. Extrayendo infer.py del contenedor...")
run("docker exec documusic_backend cat /opt/YuE/inference/infer.py > /tmp/infer_to_fix.py")

print("2. Arreglando el archivo localmente en el host...")
FIX_SCRIPT = """
with open('/tmp/infer_to_fix.py', 'r') as f:
    code = f.read()

code = code.replace('codec_# model.to(device) [DISABLED FOR 8BIT]', 'codec_model.to(device)')

with open('/tmp/infer_fixed.py', 'w') as f:
    f.write(code)
"""
client.exec_command(f"cat << 'EOF' > /tmp/do_fix.py\n{FIX_SCRIPT}\nEOF")
run("python3 /tmp/do_fix.py")

print("3. Inyectando infer.py arreglado al contenedor...")
run("docker cp /tmp/infer_fixed.py documusic_backend:/opt/YuE/inference/infer.py")
run("docker restart documusic_backend")

print("Listo!")
client.close()
