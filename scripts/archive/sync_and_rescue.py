import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

def run(cmd):
    client.exec_command(f"echo {PASS} | sudo -S bash -c '{cmd}'")

print("Sincronizando parches finales en el servidor de Madrid...")

# 1. Leer el main_madrid.py local que tiene los fixes de 2000 tokens y --disable_offload_model
with open('c:\\Users\\julio\\Documents\\Proyectos\\documusic\\main_madrid.py', 'r') as f:
    local_main = f.read()

# 2. Adaptar rutas de laptop a rutas de container
# En el laptop MODELS_DIR es c:/opt/YuE/models, en el container es /app/models
container_main = local_main.replace('c:/opt/YuE/models', '/app/models')
container_main = container_main.replace('c:/Users/julio/Documents/Proyectos/documusic/output', '/app/outputs')
container_main = container_main.replace('env["ATTENTION_IMPLEMENTATION"] = "eager"', 'env["ATTENTION_IMPLEMENTATION"] = "sdpa"')

# 3. Subir y reemplazar
with open('main_to_upload.py', 'w') as f:
    f.write(container_main)

sftp = client.open_sftp()
sftp.put('main_to_upload.py', 'main_fixed.py')

print("Inyectando main.py en el contenedor...")
run("docker cp main_fixed.py documusic_backend:/app/main.py")

# 4. Rescatar la canción generada (af8498c6) si existe
RESCUE_SCRIPT = """
import glob
import shutil
import os
job_id = 'af8498c6'
target = f'/app/outputs/{job_id}.mp3'
if not os.path.exists(target):
    audios = glob.glob(f'/app/outputs/{job_id}/**/*.mp3', recursive=True)
    if audios:
        shutil.copy(audios[0], target)
        print(f'Rescatada: {target}')
"""
client.exec_command(f"cat << 'EOF' > /tmp/rescue.py\n{RESCUE_SCRIPT}\nEOF")
run("docker cp /tmp/rescue.py documusic_backend:/tmp/rescue.py")
run("docker exec documusic_backend python3 /tmp/rescue.py")

print("Reiniciando servidor de API...")
run("docker restart documusic_backend")

print("Todo listo!")
client.close()
