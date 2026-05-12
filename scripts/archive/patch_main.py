import paramiko

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

import re

# Buscar el bloque de código que busca el WAV
old_code = """                    jobs[job_id]["logs"].append("Convirtiendo a MP3...")
                    wavs = glob.glob(f"{output_path}/**/*.wav", recursive=True)
                    if not wavs:
                        wavs = glob.glob(f"{output_path}/*.wav")
                    if wavs:
                        mp3_path = f"{OUTPUT_DIR}/{job_id}.mp3"
                        subprocess.run(
                            ["ffmpeg", "-y", "-i", wavs[0], "-b:a", "192k", mp3_path],
                            check=True
                        )
                        jobs[job_id].update({
                            "status": "done",
                            "audio_url": f"/outputs/{job_id}.mp3"
                        })
                        jobs[job_id]["logs"].append("Cancion lista!")
                    else:
                        jobs[job_id].update({"status": "error", "error": "No se encontro WAV"})"""

new_code = """                    jobs[job_id]["logs"].append("Buscando audio generado...")
                    # YuE ahora exporta directamente a MP3, buscar ambos formatos por si acaso
                    audios = glob.glob(f"{output_path}/**/*.mp3", recursive=True) + glob.glob(f"{output_path}/**/*.wav", recursive=True)
                    
                    if audios:
                        import shutil
                        mp3_path = f"{OUTPUT_DIR}/{job_id}.mp3"
                        
                        if audios[0].endswith(".wav"):
                            subprocess.run(["ffmpeg", "-y", "-i", audios[0], "-b:a", "192k", mp3_path], check=True)
                        else:
                            shutil.copy(audios[0], mp3_path)
                            
                        jobs[job_id].update({
                            "status": "done",
                            "audio_url": f"/outputs/{job_id}.mp3"
                        })
                        jobs[job_id]["logs"].append("Cancion lista!")
                    else:
                        jobs[job_id].update({"status": "error", "error": "No se encontro el audio generado"})"""

if old_code in content:
    content = content.replace(old_code, new_code)
    with sftp.file(remote_file, 'w') as f:
        f.write(content.encode('utf-8'))
    print("PATCH OK")
else:
    print("NOT FOUND. Probando expresión regular.")
    # Si la identacion es diferente o algo
    pass

sftp.close()

# Reiniciar el backend para cargar el nuevo main.py
client.exec_command("echo pepe1234 | sudo -S docker restart documusic_backend")
client.close()
