import paramiko, os

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

sftp = client.open_sftp()
remote_path = "/home/pepe/documusic/outputs/4033b56e/vocoder/mix/American-Country_tp0@93_T1@0_rp1@1_maxtk3000_4df857ed-e2ca-4ac2-9a69-fedea4d1b8a4_mixed.mp3"
local_path = os.path.join(os.environ["USERPROFILE"], "Desktop", "Cancion_Madrid.mp3")

print(f"Descargando de {remote_path} a {local_path}...")
sftp.get(remote_path, local_path)

sftp.close()
client.close()
print("¡Descarga completada con éxito!")
