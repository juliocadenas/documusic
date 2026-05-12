"""Parchea infer.py para evitar CUDA error al mover modelo a CPU."""
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
    if err.strip() and code != 0:
        print(f"ERR [{code}]: {err[:500]}")
    return out, err, code

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=15)

# 1. Check the line that does model.cpu()
run(c, "docker exec documusic_backend grep -n 'model.cpu\\|model.to.*cpu\\|del model\\|empty_cache' /opt/YuE/inference/infer.py 2>&1")

# 2. Show context around line 257
run(c, "docker exec documusic_backend sed -n '250,270p' /opt/YuE/inference/infer.py 2>&1")

# 3. Patch: Replace model.cpu() with del model + empty_cache
# This avoids the CUDA error when moving a large model back to CPU
run(c, """docker exec documusic_backend bash -c "cd /opt/YuE/inference && sed -i 's/^model.cpu()$/import gc; del model; gc.collect(); torch.cuda.empty_cache(); print(\\\"Stage 1 model freed from GPU\\\")/g' infer.py && echo 'Patched OK'" """)

# Also try a simpler approach - just wrap in try/except
run(c, """docker exec documusic_backend bash -c "cd /opt/YuE/inference && cat infer.py | grep 'model.cpu' | head -5" """)

# 4. Verify
run(c, "docker exec documusic_backend sed -n '250,270p' /opt/YuE/inference/infer.py 2>&1")

# 5. Restart
run(c, "docker restart documusic_backend 2>&1")
time.sleep(15)

# 6. Verify online
run(c, "curl -s http://localhost:8000/api 2>&1 | head -3")

c.close()
print("\nDone. Ready to test again.")
