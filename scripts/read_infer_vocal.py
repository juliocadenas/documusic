"""Read infer.py from inside the container to understand vocal handling."""
import paramiko

def run(ssh, cmd, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip(): print(out.strip()[:3000])
    if err.strip(): print(f"  ⚠ {err.strip()[:500]}")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.103.141.33", username="pepe", password="pepe1234")

# Find infer.py inside container
print("=== Finding infer.py ===")
run(ssh, "docker exec documusic_backend find /opt/YuE -name 'infer.py' -type f")

# Read the vocal handling section
print("\n=== Infer.py lines 250-350 (output/vocal handling) ===")
run(ssh, "docker exec documusic_backend sed -n '250,350p' /opt/YuE/inference/infer.py")

# Read the prompt construction section
print("\n=== Infer.py lines 180-230 (prompt construction) ===")
run(ssh, "docker exec documusic_backend sed -n '180,230p' /opt/YuE/inference/infer.py")

# Read the codec/decoder section
print("\n=== Infer.py lines 350-450 (codec decoding) ===")
run(ssh, "docker exec documusic_backend sed -n '350,450p' /opt/YuE/inference/infer.py")

# Check if there's a separate vocal decoder
print("\n=== Vocal decoder references ===")
run(ssh, "docker exec documusic_backend grep -n 'vocal\\|vtrack\\|decode\\|codec\\|xcodec\\|rearrange' /opt/YuE/inference/infer.py | head -40")

# Check the stage2 model handling
print("\n=== Stage2 handling ===")
run(ssh, "docker exec documusic_backend grep -n 'stage2\\|stage_2\\|Stage2\\|s2\\|stage2_model' /opt/YuE/inference/infer.py | head -20")

ssh.close()
print("\n🏁 Done!")
