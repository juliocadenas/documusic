import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

stdin, stdout, stderr = client.exec_command("lsmod | grep -i nvidia")
print("--- lsmod ---")
print(stdout.read().decode('utf-8'))

stdin, stdout, stderr = client.exec_command("system76-power graphics")
print("--- system76-power ---")
print(stdout.read().decode('utf-8'))

client.close()
