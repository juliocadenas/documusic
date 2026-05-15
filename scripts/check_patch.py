"""Check the patched infer.py to debug device mismatch."""
import paramiko

def run(ssh, cmd, timeout=30):
    print(f"\n>>> {cmd}")
    try:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode('utf-8', errors='replace').strip()
        if out:
            print(out[:5000])
        return out
    except Exception as e:
        print(f"[ERROR] {e}")
        return ""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234')

# 1. Check the patched from_pretrained calls
print("=" * 60)
print("PATCHED from_pretrained CALLS")
print("=" * 60)
run(ssh, "docker exec documusic_backend grep -n -A8 'from_pretrained\\|_yue_load\\|YUE_USE_8BIT' /opt/YuE/inference/infer.py | head -60")

# 2. Check the .to(device) calls
print("\n" + "=" * 60)
print("PATCHED .to(device) CALLS")
print("=" * 60)
run(ssh, "docker exec documusic_backend grep -n '\\.to(\\|YUE_USE_8BIT\\|device_map\\|load_in_8bit' /opt/YuE/inference/infer.py | head -30")

# 3. Check the patch marker
print("\n" + "=" * 60)
print("PATCH MARKER")
print("=" * 60)
run(ssh, "docker exec documusic_backend grep -n 'yue_.*_applied\\|cond_quant' /opt/YuE/inference/infer.py")

# 4. Check the full model loading section
print("\n" + "=" * 60)
print("MODEL LOADING SECTION")
print("=" * 60)
run(ssh, "docker exec documusic_backend grep -n -B2 -A15 'from_pretrained\\|stage1_model\\|stage2_model' /opt/YuE/inference/infer.py | head -80")

ssh.close()
print("\nDone.")
