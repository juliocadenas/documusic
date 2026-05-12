import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

stdin, stdout, stderr = client.exec_command("cat /etc/crypttab")
crypttab = stdout.read().decode('utf-8')

stdin, stdout, stderr = client.exec_command("lsblk -f")
lsblk = stdout.read().decode('utf-8')

print("--- crypttab ---")
print(crypttab)
print("--- lsblk ---")
print(lsblk)

client.close()
