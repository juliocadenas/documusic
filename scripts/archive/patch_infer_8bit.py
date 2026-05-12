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
    return stdout.read().decode('utf-8', errors='replace')

print("1. Instalando bitsandbytes y accelerate para compresion de 8-bits...")
run("docker exec documusic_backend pip install bitsandbytes accelerate")

print("2. Descargando infer.py original...")
client.exec_command("docker exec documusic_backend cat /opt/YuE/inference/infer.py > /tmp/infer.py")

print("3. Aplicando parche de memoria 8-bit...")
PATCH_SCRIPT = """
import sys
with open('/tmp/infer.py', 'r') as f:
    code = f.read()

# Parchear Stage 1
code = code.replace(
    'attn_implementation="eager", # To enable flashattn, you have to install flash-attn\\n    # device_map="auto",',
    'attn_implementation="eager",\\n    load_in_8bit=True,\\n    device_map="auto",'
)
code = code.replace('model.to(device)', '# model.to(device) [DISABLED FOR 8BIT]')

with open('/tmp/infer_patched.py', 'w') as f:
    f.write(code)
"""
client.exec_command(f"cat << 'EOF' > /tmp/do_patch.py\n{PATCH_SCRIPT}\nEOF")
run("python3 /tmp/do_patch.py")

print("4. Inyectando infer.py parcheado al contenedor...")
run("docker cp /tmp/infer_patched.py documusic_backend:/opt/YuE/inference/infer.py")
run("docker restart documusic_backend")

print("Listo! Parche 8-bit aplicado.")
client.close()
