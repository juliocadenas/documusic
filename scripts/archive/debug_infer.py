"""Diagnostica infer.py y descarga xcodec si falta."""
import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

def run(client, cmd, timeout=60):
    print(f"\n> {cmd}")
    _, o, e = client.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    code = o.channel.recv_exit_status()
    if out.strip():
        print(out[:2000])
    if err.strip() and code != 0:
        print(f"ERR: {err[:500]}")
    print(f"  [exit: {code}]")
    return out, err, code

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=15)

# 1. Check full argument list of infer.py
run(c, "docker exec documusic_backend grep -n 'add_argument' /opt/YuE/inference/infer.py 2>&1")

# 2. Check xcodec submodule status
run(c, "docker exec documusic_backend ls -laR /opt/YuE/inference/xcodec_mini_infer/ 2>&1 | head -40")

# 3. Check if xcodec needs to be downloaded
run(c, "docker exec documusic_backend bash -c 'cd /opt/YuE && git submodule status 2>&1'")

# 4. Check what models/codec files exist
run(c, "docker exec documusic_backend find /opt/YuE -name '*.pth' -o -name '*.pt' -o -name 'config.yaml' 2>&1 | head -20")

# 5. Check the vocoder and codec model requirements
run(c, "docker exec documusic_backend cat /opt/YuE/inference/infer.py 2>&1 | grep -A2 'basic_model_config\\|resume_path\\|vocoder\\|codec_model' | head -30")

c.close()
print("\nDone.")
