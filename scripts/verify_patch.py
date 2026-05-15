"""Verify .to(device) patch was applied correctly."""
import paramiko

def run(ssh, cmd, timeout=30):
    print(f"\n>>> {cmd}")
    try:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode('utf-8', errors='replace').strip()
        if out:
            print(out[:3000])
        return out
    except Exception as e:
        print(f"[ERROR] {e}")
        return ""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234')

# Check .to(device) lines
print("=" * 60)
print("MODEL .to(device) LINES")
print("=" * 60)
run(ssh, "docker exec documusic_backend grep -n 'model.*\\.to(\\|YUE_USE_8BIT\\|yue_.*_applied' /opt/YuE/inference/infer.py")

# Check lines 143-147 (stage1 model loading)
print("\n" + "=" * 60)
print("STAGE1 LOADING (lines 138-150)")
print("=" * 60)
run(ssh, "docker exec documusic_backend sed -n '138,150p' /opt/YuE/inference/infer.py")

# Check lines 316-327 (stage2 model loading)
print("\n" + "=" * 60)
print("STAGE2 LOADING (lines 316-327)")
print("=" * 60)
run(ssh, "docker exec documusic_backend sed -n '316,327p' /opt/YuE/inference/infer.py")

ssh.close()
print("\nDone.")
