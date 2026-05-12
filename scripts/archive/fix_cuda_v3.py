"""Parchea infer.py subiendo un script Python al contenedor."""
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

# The patch script content
PATCH_SCRIPT = """
import os
filepath = '/opt/YuE/inference/infer.py'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
patched = False
for line in lines:
    if line.strip() == 'model.cpu()':
        new_lines.append('    # model.cpu() removed - CUDA fix for RTX 5080\n')
        patched = True
        print(f'PATCHED line: {line.strip()}')
    else:
        new_lines.append(line)

if patched:
    with open(filepath, 'w') as f:
        f.writelines(new_lines)
    print('SUCCESS: model.cpu() commented out')
else:
    print('WARNING: model.cpu() not found')
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=15)

# Upload the patch script to the container via SFTP
# First write to host, then docker cp
with open("/tmp/patch_infer.py", "w") as f:
    f.write(PATCH_SCRIPT)

sftp = c.open_sftp()
sftp.put("/tmp/patch_infer.py", "/home/pepe/documusic/patch_infer.py")
sftp.close()

# Copy into container and run
run(c, "docker cp /home/pepe/documusic/patch_infer.py documusic_backend:/tmp/patch_infer.py 2>&1")
run(c, "docker exec documusic_backend python3 /tmp/patch_infer.py 2>&1")

# Verify
run(c, "docker exec documusic_backend sed -n '254,262p' /opt/YuE/inference/infer.py 2>&1")

# Restart
run(c, "docker restart documusic_backend 2>&1")
time.sleep(15)

# Verify online
run(c, "curl -s http://localhost:8000/api 2>&1 | head -3")

c.close()
print("\nDone. Ready to test.")
