"""Check if vocal and instrumental decoder files exist on server."""
import paramiko

def run(ssh, cmd, timeout=30):
    print(f"  → {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip(): print(f"  ← {out.strip()[:2000]}")
    if err.strip(): print(f"  ⚠ {err.strip()[:500]}")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.103.141.33", username="pepe", password="pepe1234")

# 1. Check decoder files
print("=== Decoder files ===")
run(ssh, "docker exec documusic_backend find /opt/YuE -name 'decoder_*.pth' -exec ls -la {} \\;")
run(ssh, "docker exec documusic_backend find /app/models -name 'decoder_*.pth' -exec ls -la {} \\;")

# 2. Check xcodec_mini_infer/decoders directory
print("\n=== xcodec decoders directory ===")
run(ssh, "docker exec documusic_backend find /opt/YuE -path '*/decoders/*' -type f | head -20")
run(ssh, "docker exec documusic_backend find /app/models -path '*/decoders/*' -type f | head -20")

# 3. Read the vocoder.py to understand how decoders are used
print("\n=== vocoder.py ===")
run(ssh, "docker exec documusic_backend find /opt/YuE -name 'vocoder.py' -type f")
run(ssh, "docker exec documusic_backend cat /opt/YuE/inference/xcodec_mini_infer/vocoder.py 2>/dev/null | head -80")

# 4. Read the process_audio function
print("\n=== process_audio function ===")
run(ssh, "docker exec documusic_backend grep -n 'def process_audio\\|vocal_decoder\\|inst_decoder\\|decoder_131\\|decoder_151' /opt/YuE/inference/xcodec_mini_infer/vocoder.py 2>/dev/null")

# 5. Check the infer.py code that calls the vocoder
print("\n=== Infer.py vocoder calls ===")
run(ssh, "docker exec documusic_backend grep -n 'process_audio\\|vocal_decoder\\|inst_decoder\\|build_codec\\|vocoder' /opt/YuE/inference/infer.py | head -20")

# 6. Read the vocoder section of infer.py
print("\n=== Infer.py vocoder section (lines 400-500) ===")
run(ssh, "docker exec documusic_backend sed -n '390,500p' /opt/YuE/inference/infer.py")

ssh.close()
print("\n🏁 Done!")
