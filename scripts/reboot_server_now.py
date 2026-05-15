"""Reboot server to fix read-only filesystem."""
import paramiko
import time

def run(ssh, cmd, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode().strip(), stderr.read().decode().strip()

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.103.141.33", username="pepe", password="pepe1234")

# Force reboot with sudo
print("=== FORCING REBOOT ===")
stdin, stdout, stderr = ssh.exec_command("echo 'pepe1234' | sudo -S reboot -f", timeout=10)
try:
    print(stdout.read().decode().strip())
except:
    pass
print("Reboot command sent!")

ssh.close()

# Wait for server to come back
print("\n=== WAITING FOR SERVER (60s) ===")
time.sleep(60)

for attempt in range(20):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect("100.103.141.33", username="pepe", password="pepe1234", timeout=10)
        out, _ = run(ssh, "uptime")
        print(f"Server back! {out}")
        
        # Test write
        out, err = run(ssh, "touch /tmp/test_write && echo 'WRITE OK' && rm /tmp/test_write")
        print(f"Write test: {out}")
        if err:
            print(f"  Error: {err}")
        
        # Start container
        print("\n=== STARTING CONTAINER ===")
        out, err = run(ssh, "cd ~/documusic && docker-compose up -d", timeout=60)
        print(out)
        if err:
            print(f"  {err[:300]}")
        
        # Wait for backend
        print("\n=== WAITING FOR BACKEND ===")
        for i in range(30):
            time.sleep(3)
            out, _ = run(ssh, "curl -s http://localhost:8000/ | head -1", timeout=5)
            if '"status"' in out:
                print(f"Backend UP after {i*3}s")
                break
        else:
            print("Backend FAILED to start!")
        
        # Final test
        print("\n=== CONTAINER WRITE TEST ===")
        out, err = run(ssh, "docker exec documusic_backend bash -c 'touch /app/outputs/test && echo OK && rm /app/outputs/test' 2>&1")
        print(out)
        if err:
            print(f"  {err}")
        
        ssh.close()
        break
    except Exception as e:
        print(f"  Attempt {attempt+1}: {e}")
        time.sleep(10)
