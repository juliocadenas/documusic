"""Verifica estado de xcodec y descarga si es necesario."""
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
    if err.strip():
        print(f"ERR [{code}]: {err[:800]}")
    return out, err, code

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=15)

# Check current state
print("ESTADO ACTUAL de xcodec_mini_infer:")
run(c, "docker exec documusic_backend ls -laR /opt/YuE/inference/xcodec_mini_infer/ 2>&1 | head -40")

# Check if git submodule init is running
run(c, "ps aux | grep -i 'git\|xcodec\|clone' | grep -v grep 2>&1")

# Try the submodule init with more verbose output
print("\nIntentando git submodule init...")
out, err, code = run(c, "docker exec documusic_backend bash -c 'cd /opt/YuE && cat .gitmodules 2>&1'")

# Try alternative: check if xcodec is in a different location
run(c, "docker exec documusic_backend bash -c 'find /opt/YuE -name \".git\" -type d 2>&1 | head -10'")

# The xcodec_mini_infer might need to be cloned from its actual repo
# Let's check the YuE repo's .gitmodules for the correct URL
run(c, "docker exec documusic_backend bash -c 'cd /opt/YuE && git config --file .gitmodules --list 2>&1'")

c.close()
print("\nDone.")
