import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

stdin, stdout, stderr = client.exec_command("dmesg | grep -i 'nvidia\\|nvrm\\|pcie'")
print("--- dmesg ---")
print(stdout.read().decode('utf-8'))

client.close()
