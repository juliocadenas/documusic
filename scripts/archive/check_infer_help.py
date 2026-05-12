import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

stdin, stdout, stderr = client.exec_command("echo pepe1234 | sudo -S docker exec documusic_backend python3 /opt/YuE/inference/infer.py --help")
print("--- infer.py help ---")
print(stdout.read().decode('utf-8'))

client.close()
