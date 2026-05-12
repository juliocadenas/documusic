import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

sftp = client.open_sftp()
sftp.put("c:\\Users\\julio\\Documents\\Proyectos\\documusic\\main_madrid.py", "/home/pepe/documusic/backend/main.py")
sftp.close()

# Reiniciar backend
client.exec_command("echo pepe1234 | sudo -S docker restart documusic_backend")
client.close()
print("main.py subido y servidor reiniciado")
