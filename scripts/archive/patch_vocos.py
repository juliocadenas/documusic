import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

print("Parcheando pretrained.py en el contenedor...")
cmd = """echo pepe1234 | sudo -S docker exec documusic_backend bash -c 'sed -i "s/feature_extractor = instantiate_class(args=(), init=config\\[\\"feature_extractor\\"\\])/if \\"feature_extractor\\" in config:\\n            feature_extractor = instantiate_class(args=(), init=config\\[\\"feature_extractor\\"\\])\\n        else:\\n            feature_extractor = None/" /opt/YuE/inference/vocos/pretrained.py'"""

stdin, stdout, stderr = client.exec_command(cmd)
print("Salida:", stdout.read().decode('utf-8'))
print("Error:", stderr.read().decode('utf-8'))

print("Verificando el parche...")
stdin, stdout, stderr = client.exec_command("echo pepe1234 | sudo -S docker exec documusic_backend bash -c 'cat /opt/YuE/inference/vocos/pretrained.py | grep feature_extractor'")
print("Cat:", stdout.read().decode('utf-8'))

client.close()
