import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

script = """import os
path = '/opt/YuE/inference/vocos/pretrained.py'
with open(path, 'r') as f:
    c = f.read()

# Deshacer el parche anterior si existe
c = c.replace('if "feature_extractor" in config:\\n            feature_extractor = instantiate_class(args=(), init=config["feature_extractor"])\\n            feature_extractor = None', 'feature_extractor = instantiate_class(args=(), init=config["feature_extractor"])')
c = c.replace('if "feature_extractor" in config:\\n            feature_extractor = instantiate_class(args=(), init=config["feature_extractor"])\\n        else:\\n            feature_extractor = None', 'feature_extractor = instantiate_class(args=(), init=config["feature_extractor"])')

# Aplicar el nuevo parche correctamente
old = 'feature_extractor = instantiate_class(args=(), init=config["feature_extractor"])'
new = '''if "feature_extractor" in config:
            feature_extractor = instantiate_class(args=(), init=config["feature_extractor"])
        else:
            feature_extractor = None'''

if old in c:
    c = c.replace(old, new)
    with open(path, 'w') as f:
        f.write(c)
    print("PATCH OK")
else:
    print("NOT FOUND")
"""

stdin, stdout, stderr = client.exec_command("echo pepe1234 | sudo -S docker exec -i documusic_backend python3 -c \"{}\"".format(script.replace('"', '\\"').replace('$', '\\$')))
print(stdout.read().decode('utf-8'))
print(stderr.read().decode('utf-8'))
client.close()
