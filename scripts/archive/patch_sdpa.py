import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

def run(cmd):
    client.exec_command(f"echo {PASS} | sudo -S bash -c '{cmd}'")

print("Aplicando parche final para Blackwell (RTX 5080)...")
FIX_SCRIPT = """
with open('/opt/YuE/inference/infer.py', 'r') as f:
    code = f.read()

# Quitar 8-bit y eager, poner sdpa
code = code.replace(
    'attn_implementation="eager",\\n    load_in_8bit=True,\\n    device_map="auto",',
    'attn_implementation="sdpa", # PyTorch Native Flash Attention para Blackwell\\n    # device_map="auto",'
)

# Restaurar el .to(device) original
code = code.replace(
    '# model.to(device) [DISABLED FOR 8BIT]',
    'model.to(device)'
)

with open('/tmp/infer_sdpa.py', 'w') as f:
    f.write(code)
"""
client.exec_command(f"cat << 'EOF' > /tmp/do_sdpa.py\n{FIX_SCRIPT}\nEOF")
run("python3 /tmp/do_sdpa.py")
run("docker cp /tmp/infer_sdpa.py documusic_backend:/opt/YuE/inference/infer.py")
run("docker restart documusic_backend")

print("Listo!")
client.close()
