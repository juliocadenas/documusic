import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

# Check GPU usage
stdin, stdout, stderr = client.exec_command("nvidia-smi")
smi = stdout.read().decode('utf-8')

# Check last 20 lines of docker logs
stdin, stdout, stderr = client.exec_command("docker logs --tail 20 documusic_backend")
logs = stdout.read().decode('utf-8')

print("--- NVIDIA-SMI ---")
print(smi)
print("--- DOCKER LOGS ---")
print(logs)

client.close()
