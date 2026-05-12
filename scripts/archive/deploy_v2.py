import paramiko
import os

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

LOCAL_FILE = r"c:\Users\julio\Documents\Proyectos\documusic\main_madrid.py"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print(f"Conectando a {HOST}...")
    client.connect(HOST, username=USER, password=PASS, timeout=15)
    
    # Upload main_madrid.py
    sftp = client.open_sftp()
    print(f"Subiendo {LOCAL_FILE}...")
    sftp.put(LOCAL_FILE, "/home/pepe/documusic/main.py")
    sftp.close()

    # Restart container
    print("Reiniciando contenedor con nueva config de memoria...")
    stdin, stdout, stderr = client.exec_command("cd /home/pepe/documusic && docker compose restart documusic_backend")
    print(stdout.read().decode('utf-8'))
    print(stderr.read().decode('utf-8'))
    
    # Check GPU
    stdin, stdout, stderr = client.exec_command("nvidia-smi")
    print("--- NVIDIA-SMI STATUS ---")
    print(stdout.read().decode('utf-8'))

    print("Despliegue V2 completado.")
    client.close()
except Exception as e:
    print(f"ERROR: {e}")
