import paramiko, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

def run(cmd, desc="", timeout=60):
    if desc: print(f"\n=== {desc} ===")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    combined = out + err
    if combined.strip(): print(combined[:4000])
    return out

run('echo pepe1234 | sudo -S docker restart documusic_backend', 'Reiniciando el backend para aplicar librerías de audio')
client.close()
