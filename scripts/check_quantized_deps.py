"""Check if ACE-Step quantized=True needs bitsandbytes or other deps."""
import paramiko

def run(ssh, cmd, timeout=30):
    print(f"\n>>> {cmd}")
    try:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode('utf-8', errors='replace').strip()
        err = stderr.read().decode('utf-8', errors='replace').strip()
        if out:
            print(out)
        if err:
            print(f"[STDERR] {err}")
        return out
    except Exception as e:
        print(f"[ERROR] {e}")
        return ""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234')

# 1. Check what quantized=True does in ACE-Step pipeline
print("=" * 60)
print("ACE-STEP PIPELINE QUANTIZED CODE")
print("=" * 60)
run(ssh, "grep -n 'quantized' /home/pepe/AI_MODELS/ace-step/acestep/pipeline_ace_step.py | head -20")

# 2. Check if bitsandbytes is installed
print("\n" + "=" * 60)
print("BITSANDBYTES CHECK")
print("=" * 60)
run(ssh, "docker exec documusic_backend pip3 show bitsandbytes 2>&1 || echo 'NOT INSTALLED'")

# 3. Check if torchao is installed (alternative quantization)
print("\n" + "=" * 60)
print("TORCHAO CHECK")
print("=" * 60)
run(ssh, "docker exec documusic_backend pip3 show torchao 2>&1 || echo 'NOT INSTALLED'")

# 4. Read the quantized-related code from pipeline
print("\n" + "=" * 60)
print("QUANTIZED CODE CONTEXT")
print("=" * 60)
run(ssh, "grep -n -A5 -B2 'quantized' /home/pepe/AI_MODELS/ace-step/acestep/pipeline_ace_step.py")

ssh.close()
print("\nDone.")
