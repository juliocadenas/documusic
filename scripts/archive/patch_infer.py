import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=15)

def run(cmd):
    stdin, stdout, stderr = c.exec_command(f"echo {PASS} | sudo -S bash -c '{cmd}'")
    return stdout.read().decode('utf-8', errors='replace'), stderr.read().decode('utf-8', errors='replace')

PATCH_SCRIPT = """
import sys

file_path = "/opt/YuE/inference/infer.py"
with open(file_path, "r", encoding="utf-8") as f:
    code = f.read()

# Replace the offload logic
old_code = '''# offload model
if not args.disable_offload_model:
    model.cpu()
    del model
    torch.cuda.empty_cache()'''

new_code = '''# Free VRAM for Stage 2 without moving to CPU (avoids PCIe crashes on RTX 5080)
try:
    del model
    import gc
    gc.collect()
    torch.cuda.empty_cache()
    print("VRAM liberada correctamente para el Stage 2.")
except Exception as e:
    print(f"Error freeing memory: {e}")'''

if old_code in code:
    code = code.replace(old_code, new_code)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(code)
    print("infer.py parcheado con exito.")
else:
    print("No se encontro el bloque a reemplazar.")
"""

c.exec_command(f"cat << 'EOF' > /tmp/patch_infer.py\n{PATCH_SCRIPT}\nEOF")
out, err = run("docker cp /tmp/patch_infer.py documusic_backend:/tmp/patch_infer.py")
out, err = run("docker exec documusic_backend python3 /tmp/patch_infer.py")
print("Resultado del parche:")
print(out)
if err: print("Error:", err)

c.close()
