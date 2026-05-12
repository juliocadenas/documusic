import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

stdin, stdout, stderr = client.exec_command("echo pepe1234 | sudo -S docker exec documusic_backend bash -c 'cat /opt/YuE/inference/infer.py | grep -A 5 -B 5 process_audio'")
print("--- infer.py process_audio calls ---")
print(stdout.read().decode('utf-8'))

client.close()
