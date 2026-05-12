"""Sube el main.py corregido y reinicia el contenedor."""
import paramiko
import time

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

def run(client, cmd, timeout=60):
    print(f"\n> {cmd[:120]}")
    _, o, e = client.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    code = o.channel.recv_exit_status()
    if out.strip():
        print(out[:1500])
    if err.strip() and code != 0:
        print(f"ERR [{code}]: {err[:500]}")
    return out, err, code

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=15)

# Upload fixed main.py
sftp = c.open_sftp()
sftp.put("backend/main.py", "/home/pepe/documusic/backend/main.py")
sftp.close()
print("Uploaded backend/main.py")

# Restart container
run(c, "docker restart documusic_backend 2>&1")
time.sleep(15)

# Verify
run(c, "curl -s http://localhost:8000/api 2>&1 | head -3")

c.close()
print("\nDone. Listo para generar de nuevo.")
