import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

def run(cmd):
    print(f"> {cmd}")
    stdin, stdout, stderr = client.exec_command(f"echo {PASS} | sudo -S {cmd}")
    print(stdout.read().decode('utf-8'))
    print(stderr.read().decode('utf-8'))

run("lspci | grep -i 'vga\\|3d\\|display\\|nvidia'")

client.close()
