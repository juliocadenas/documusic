import paramiko, sys

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

print("Instalando dependencias faltantes en el contenedor...")
stdin, stdout, stderr = client.exec_command("echo pepe1234 | sudo -S docker exec documusic_backend pip install torchcodec soundfile")
print(stdout.read().decode('utf-8'))
print(stderr.read().decode('utf-8'))

print("Reiniciando el contenedor...")
client.exec_command("echo pepe1234 | sudo -S docker restart documusic_backend")

client.close()
