"""Quick deploy: git pull + docker restart."""
import paramiko
import time

HOST = "100.103.141.33"
USER = "pepe"
PASS = "pepe1234"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)

stdin, stdout, stderr = ssh.exec_command("cd ~/documusic && git pull", timeout=30)
print(stdout.read().decode()[-500:])
print(stderr.read().decode()[-300:])

stdin, stdout, stderr = ssh.exec_command("docker restart documusic_backend", timeout=30)
print(stdout.read().decode())

time.sleep(8)

stdin, stdout, stderr = ssh.exec_command("curl -s http://localhost:8000/", timeout=15)
print(stdout.read().decode()[-500:])

ssh.close()
print("Done!")
