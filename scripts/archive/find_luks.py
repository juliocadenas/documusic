import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

stdin, stdout, stderr = client.exec_command("lsblk -o NAME,TYPE,UUID -rn | grep crypt")
print("--- lsblk crypt ---")
print(stdout.read().decode('utf-8'))

stdin, stdout, stderr = client.exec_command("blkid | grep crypto_LUKS")
print("--- blkid LUKS ---")
print(stdout.read().decode('utf-8'))

client.close()
