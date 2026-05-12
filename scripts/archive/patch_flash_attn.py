"""
Parchea infer.py de YuE para deshabilitar FlashAttention y usar eager attention.
Tambien instala flash_attn si es posible (requiere compilacion).
"""
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

print("=" * 60)
print("PARCHANDO infer.py para deshabilitar FlashAttention")
print("=" * 60)

# 1. Check current infer.py for flash attention usage
run(c, "docker exec documusic_backend grep -n 'flash\\|attn_implementation\\|FlashAttention\\|attn_impl' /opt/YuE/inference/infer.py 2>&1")

# 2. Patch the infer.py to use eager attention instead of flash
# The key line is where it loads the model with AutoModelForCausalLM.from_pretrained
# We need to add attn_implementation="eager" to both model loads
patch_script = r"""
cd /opt/YuE/inference

# Backup original
cp infer.py infer.py.bak

# Patch Stage 1 model loading - add attn_implementation="eager"
sed -i 's/from_pretrained(/from_pretrained_staging(/g' infer.py

# More targeted approach: use Python to patch
python3 -c "
import re
with open('infer.py', 'r') as f:
    content = f.read()

# Find all from_pretrained calls and add attn_implementation if not present
# Pattern 1: Stage 1 model
content = content.replace(
    'model = AutoModelForCausalLM.from_pretrained(',
    'model = AutoModelForCausalLM.from_pretrained('
)

# Add attn_implementation='eager' to model loading
# Find the line with stage1_model and add attn_implementation
lines = content.split('\n')
new_lines = []
for i, line in enumerate(lines):
    new_lines.append(line)
    if 'AutoModelForCausalLM.from_pretrained(' in line and 'stage1_model' not in line:
        # Check if next lines contain the model path
        if i + 1 < len(lines) and 'stage1_model' in lines[i + 1]:
            new_lines.append('    attn_implementation=\"eager\",')
    if 'AutoModelForCausalLM.from_pretrained(' in line and 'stage2' in line.lower():
        new_lines.append('    attn_implementation=\"eager\",')
    # Also check for the actual pattern in YuE's infer.py
    if 'stage1_model,' in line and 'from_pretrained' not in line:
        # This is inside a from_pretrained call, add attn_implementation after
        new_lines.append('        attn_implementation=\"eager\",')

with open('infer.py', 'w') as f:
    f.write('\n'.join(new_lines))
print('Patched!')
"
"""

# Actually, let's do a simpler approach - just set the environment variable
# and also patch the specific lines

# 3. Simple approach: Set environment variable to disable flash attention
# And patch the model config to not require it
print("\nEnfoque: Modificar infer.py directamente...")

# First, let's see the exact lines around the model loading
out, _, _ = run(c, "docker exec documusic_backend sed -n '80,100p' /opt/YuE/inference/infer.py 2>&1")
print("Current model loading code:")
print(out)

# Now patch - replace flash_attention_2 with eager in the code
run(c, """docker exec documusic_backend bash -c "cd /opt/YuE/inference && cp infer.py infer.py.bak && sed -i 's/flash_attention_2/eager/g; s/FlashAttention2/EagerAttention/g; s/attn_implementation=\\\"flash_attention_2\\\"/attn_implementation=\\\"eager\\\"/g' infer.py && echo 'Patched OK'" """)

# Also patch: if the model config has attn_implementation set, override it
run(c, """docker exec documusic_backend bash -c "cd /opt/YuE/inference && sed -i 's/attn_implementation={}/attn_implementation=\"eager\"/g' infer.py && echo 'OK'" """)

# 4. Verify the patch
print("\nVerificando parche...")
run(c, "docker exec documusic_backend sed -n '80,100p' /opt/YuE/inference/infer.py 2>&1")
run(c, "docker exec documusic_backend grep -n 'flash\\|eager\\|attn' /opt/YuE/inference/infer.py 2>&1 | head -20")

# 5. Also patch the model config files to not require flash attention
# Check if the model config has _attn_implementation
run(c, "docker exec documusic_backend find /app/models -name 'config.json' 2>&1 | head -5")
out, _, _ = run(c, "docker exec documusic_backend cat /app/models/YuE-s1/config.json 2>&1 | head -30")

# Patch config.json if it has flash attention setting
run(c, """docker exec documusic_backend bash -c "find /app/models -name config.json -exec sed -i 's/flash_attention_2/eager/g' {} \\; && echo 'Config patched'" """)

# 6. Test again
print("\n" + "=" * 60)
print("Probando generacion despues del parche...")
print("=" * 60)

# Restart container to pick up changes
run(c, "docker restart documusic_backend 2>&1")
time.sleep(15)

# Check it's back online
run(c, "curl -s http://localhost:8000/api 2>&1 | head -5")

c.close()
print("\nDone. Run test_generate.py again to test.")
