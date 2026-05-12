"""Parchea infer.py usando Python para reemplazar model.cpu() correctamente."""
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

# Use Python to patch the file properly
patch_script = """
cd /opt/YuE/inference
python3 -c "
with open('infer.py', 'r') as f:
    content = f.read()

# Replace the problematic block:
# if not args.disable_offload_model:
#     model.cpu()
#     del model
#     torch.cuda.empty_cache()
# With:
# if not args.disable_offload_model:
#     del model
#     torch.cuda.empty_cache()

old_block = '''    model.cpu()
    del model
    torch.cuda.empty_cache()'''

new_block = '''    # model.cpu() removed - was causing CUDA error on RTX 5080
    del model
    torch.cuda.empty_cache()'''

if old_block in content:
    content = content.replace(old_block, new_block)
    with open('infer.py', 'w') as f:
        f.write(content)
    print('PATCHED: model.cpu() removed successfully')
else:
    print('WARNING: Could not find exact block to patch')
    # Try line-by-line approach
    lines = content.split('\\n')
    new_lines = []
    for line in lines:
        if line.strip() == 'model.cpu()':
            new_lines.append('    # model.cpu() removed - CUDA fix')
            print('PATCHED: model.cpu() line found and commented out')
        else:
            new_lines.append(line)
    content = '\\n'.join(new_lines)
    with open('infer.py', 'w') as f:
        f.write(content)
"
"""

run(c, f"docker exec documusic_backend bash -c '{patch_script}'")

# Verify
run(c, "docker exec documusic_backend sed -n '254,262p' /opt/YuE/inference/infer.py 2>&1")

# Restart
run(c, "docker restart documusic_backend 2>&1")
time.sleep(15)

# Verify online
run(c, "curl -s http://localhost:8000/api 2>&1 | head -3")

c.close()
print("\nDone.")
