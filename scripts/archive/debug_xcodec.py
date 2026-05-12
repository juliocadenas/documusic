"""Diagnostica la estructura de xcodec dentro del contenedor."""
import paramiko
import json

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

def run(client, cmd, timeout=15):
    _, o, e = client.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    code = o.channel.recv_exit_status()
    return out, err, code

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=15)

# Check xcodec structure inside container
cmds = [
    "docker exec documusic_backend find /opt/YuE -name 'config.yaml' 2>&1",
    "docker exec documusic_backend find /opt/YuE -name '*.pth' 2>&1",
    "docker exec documusic_backend find /opt/YuE -name 'xcodec*' -type d 2>&1",
    "docker exec documusic_backend ls -la /opt/YuE/inference/xcodec_mini_infer/ 2>&1",
    "docker exec documusic_backend find /opt/YuE/inference/xcodec_mini_infer -type f 2>&1 | head -30",
    "docker exec documusic_backend ls -la /opt/YuE/inference/xcodec_mini_infer/final_ckpt/ 2>&1",
    # Also check the infer.py to see what arguments it expects
    "docker exec documusic_backend head -80 /opt/YuE/inference/infer.py 2>&1",
]

for cmd in cmds:
    print(f"\n{'='*60}")
    print(f"CMD: {cmd}")
    print('='*60)
    out, err, code = run(c, cmd, timeout=15)
    if out.strip():
        print(out[:1500])
    if err.strip():
        print(f"ERR: {err[:500]}")

c.close()
print("\nDone.")
