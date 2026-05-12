import paramiko, sys

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

sftp = client.open_sftp()
remote_file = "/home/pepe/documusic/backend/main.py"

with sftp.file(remote_file, 'r') as f:
    content = f.read().decode('utf-8')

inject_code = """def run_yue_inference(job_id: str, lyrics: str, style_prompt: str):
    try:
        # --- FIX: VALIDACION ESTRICTA DE GPU ---
        import subprocess
        try:
            subprocess.run(["nvidia-smi"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            jobs[job_id]["logs"].append("Validacion OK: GPU RTX 5080 detectada y activa.")
        except Exception:
            jobs[job_id]["logs"].append("ERROR: No se detecto GPU. Cancelando para evitar uso de CPU.")
            jobs[job_id].update({"status": "error", "error": "GPU inactiva. Cancelado para evitar horas de procesamiento CPU."})
            return
"""

new_content = content.replace("def run_yue_inference(job_id: str, lyrics: str, style_prompt: str):\n    try:", inject_code)

with sftp.file(remote_file, 'w') as f:
    f.write(new_content.encode('utf-8'))

print("Archivo modificado remotamente.")
sftp.close()

stdin, stdout, stderr = client.exec_command("echo pepe1234 | sudo -S docker restart documusic_backend")
print("Contenedor reiniciado: " + stdout.read().decode('utf-8'))

client.close()
