import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

script = """
if [ -f /etc/cryptsetup-initramfs/conf-hook ]; then
    echo "EXISTS"
else
    echo "DOES NOT EXIST"
fi
"""

stdin, stdout, stderr = client.exec_command("echo pepe1234 | sudo -S bash -c '{}'".format(script.replace("'", "'\\''")))
print(stdout.read().decode('utf-8'))

client.close()
