import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

sftp = client.open_sftp()
sftp.get("/home/pepe/documusic/backend/main.py", "c:\\Users\\julio\\Documents\\Proyectos\\documusic\\main_madrid.py")
sftp.close()
client.close()
print("main.py descargado")
