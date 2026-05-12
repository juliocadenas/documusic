"""Parchea model.cpu() usando sed directo en el contenedor."""
import paramiko
import time

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

def run(client, cmd, timeout=60):
    print(f"\n> {cmd[:150]}")
    _, o, e = client.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    code = o.channel.recv_exit_status()
    if out.strip():
        print(out[:2000])
    if err.strip():
        print(f"ERR: {err[:500]}")
    return out, err, code

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=15)

# Use sed to comment out model.cpu() - simple replacement
# The line is exactly "    model.cpu()" (4 spaces indent)
run(c, 'docker exec documusic_backend sed -i "/^    model.cpu()/s/model.cpu()/# model.cpu() # CUDA fix/" /opt/YuE/inference/infer.py 2>&1')

# Verify
run(c, "docker exec documusic_backend sed -n '254,262p' /opt/YuE/inference/infer.py 2>&1")

# Restart
run(c, "docker restart documusic_backend 2>&1")
time.sleep(15)

# Verify online
run(c, "curl -s http://localhost:8000/api 2>&1 | head -3")

c.close()
print("\nDone.")
