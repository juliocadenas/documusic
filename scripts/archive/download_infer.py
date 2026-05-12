import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')
HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

sftp = client.open_sftp()
sftp.get("/opt/YuE/inference/infer.py", "c:\\Users\\julio\\Documents\\Proyectos\\documusic\\infer.py")
sftp.close()
client.close()
print("Descarga completada")
