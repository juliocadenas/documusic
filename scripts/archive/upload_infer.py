import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')
HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

def run(cmd):
    client.exec_command(f"echo {PASS} | sudo -S bash -c '{cmd}'")

print("Subiendo archivo arreglado...")
sftp = client.open_sftp()
sftp.put('c:\\Users\\julio\\Documents\\Proyectos\\documusic\\infer_current_fixed.py', 'infer_to_upload.py')
sftp.close()

print("Inyectando en Docker y reiniciando...")
run("docker cp infer_to_upload.py documusic_backend:/opt/YuE/inference/infer.py")
run("docker restart documusic_backend")

print("Terminado!")
client.close()
