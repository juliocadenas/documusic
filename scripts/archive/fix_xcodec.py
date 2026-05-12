"""
Descarga e instala los archivos de xcodec_mini_infer dentro del contenedor.
xcodec es un submodulo de YuE que no se clono correctamente.
"""
import paramiko
import time

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

def run(client, cmd, timeout=300):
    print(f"\n> {cmd[:120]}...")
    _, o, e = client.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    code = o.channel.recv_exit_status()
    if out.strip():
        print(out[:1500])
    if err.strip() and code != 0:
        print(f"ERR: {err[:800]}")
    print(f"  [exit: {code}]")
    return out, err, code

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=15)

print("=" * 60)
print("CORRECCION: Descargando xcodec_mini_infer para YuE")
print("=" * 60)

# Step 1: Check if xcodec_mini_infer is a separate repo we can clone
# The xcodec_mini_infer is actually at: https://github.com/jishengpeng/xcodec_mini_infer
# But it's referenced as a submodule in YuE

# Step 2: Try to initialize the submodule inside the container
run(c, "docker exec documusic_backend bash -c 'cd /opt/YuE && git submodule update --init --recursive 2>&1'", timeout=120)

# Step 3: Check if that worked
out, _, _ = run(c, "docker exec documusic_backend ls -la /opt/YuE/inference/xcodec_mini_infer/ 2>&1")

if 'final_ckpt' not in out:
    print("\n⚠️ Submodule init failed. Trying manual clone...")
    
    # Remove empty directory and clone manually
    run(c, "docker exec documusic_backend bash -c 'rm -rf /opt/YuE/inference/xcodec_mini_infer && cd /opt/YuE/inference && git clone https://huggingface.co/m-a-p/xcodec_mini_infer 2>&1'", timeout=300)
    
    # Check again
    out, _, _ = run(c, "docker exec documusic_backend ls -la /opt/YuE/inference/xcodec_mini_infer/ 2>&1")

if 'final_ckpt' not in out:
    print("\n⚠️ HuggingFace clone failed. Trying GitHub...")
    run(c, "docker exec documusic_backend bash -c 'rm -rf /opt/YuE/inference/xcodec_mini_infer && cd /opt/YuE/inference && git clone https://github.com/multimodal-art-projection/xcodec_mini_infer 2>&1'", timeout=300)
    out, _, _ = run(c, "docker exec documusic_backend ls -la /opt/YuE/inference/xcodec_mini_infer/ 2>&1")

# Step 4: Verify the critical files
print("\n" + "=" * 60)
print("VERIFICACION FINAL")
print("=" * 60)

checks = [
    "/opt/YuE/inference/xcodec_mini_infer/final_ckpt/config.yaml",
    "/opt/YuE/inference/xcodec_mini_infer/final_ckpt/ckpt_00360000.pth",
    "/opt/YuE/inference/xcodec_mini_infer/decoders/config.yaml",
    "/opt/YuE/inference/xcodec_mini_infer/decoders/decoder_131000.pth",
    "/opt/YuE/inference/xcodec_mini_infer/models/soundstream_hubert_new.py",
]

all_ok = True
for path in checks:
    out, _, code = run(c, f"docker exec documusic_backend test -f {path} && echo 'EXISTS' || echo 'MISSING' 2>&1")
    status = "EXISTS" in out
    if not status:
        all_ok = False
    print(f"  {'✅' if status else '❌'} {path}")

# Step 5: If all good, test diagnostics
if all_ok:
    print("\n✅ Todos los archivos de xcodec están presentes!")
    out, _, _ = run(c, "curl -s http://localhost:8000/api/diagnostics 2>&1")
    print(out[:1000])
else:
    print("\n❌ Faltan archivos de xcodec. Puede necesitar descarga manual.")
    # List what we have
    run(c, "docker exec documusic_backend find /opt/YuE/inference/xcodec_mini_infer -type f 2>&1 | head -30")

# Step 6: Restart container to pick up changes
print("\nReiniciando contenedor...")
run(c, "docker restart documusic_backend 2>&1")
time.sleep(10)

# Final check
out, _, _ = run(c, "curl -s http://localhost:8000/api 2>&1")
print(out[:500])

c.close()
print("\nDone.")
