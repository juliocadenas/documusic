"""Instala torchcodec y parchea infer.py para usar soundfile como fallback."""
import paramiko
import time

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

def run(client, cmd, timeout=300):
    print(f"\n> {cmd[:150]}")
    _, o, e = client.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    code = o.channel.recv_exit_status()
    if out.strip():
        print(out[:2000])
    if err.strip() and code != 0:
        print(f"ERR [{code}]: {err[:800]}")
    return out, err, code

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=15)

# 1. Install torchcodec
print("Instalando torchcodec...")
run(c, "docker exec documusic_backend pip3 install torchcodec 2>&1", timeout=300)

# 2. If torchcodec fails, patch infer.py to use soundfile instead
out, _, code = run(c, "docker exec documusic_backend python3 -c 'import torchcodec; print(\"OK\")' 2>&1")
if "OK" not in out:
    print("\ntorchcodec no se pudo instalar. Parcheando infer.py para usar soundfile...")
    # Find where torchcodec is used in infer.py
    run(c, "docker exec documusic_backend grep -n 'torchcodec\\|save_with_torchcodec\\|torchaudio.save' /opt/YuE/inference/infer.py 2>&1")

    # Patch: replace torchcodec save with torchaudio.save
    run(c, """docker exec documusic_backend bash -c "cd /opt/YuE/inference && sed -i 's/save_with_torchcodec/torchaudio.save/g' infer.py && echo 'Patched'" """)

# 3. Restart container
print("\nReiniciando contenedor...")
run(c, "docker restart documusic_backend 2>&1")
time.sleep(15)

# 4. Verify
run(c, "curl -s http://localhost:8000/api 2>&1 | head -3")

c.close()
print("\nDone. Run test_generate.py again.")
