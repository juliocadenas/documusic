import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')
HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

stdin, stdout, stderr = client.exec_command("cat /opt/YuE/inference/infer.py | grep -i parser.add_argument")
print(stdout.read().decode('utf-8'))

client.close()
