"""Fix read-only filesystem issue on server."""
import paramiko
import time

def run(ssh, cmd, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if err and 'WARNING' not in err:
        print(f"  STDERR: {err}")
    return out

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.103.141.33", username="pepe", password="pepe1234")

# 1. Check disk space
print("=== DISK SPACE ===")
print(run(ssh, "df -h /home/pepe/documusic"))

# 2. Check outputs dir permissions
print("\n=== OUTPUTS DIR ===")
print(run(ssh, "ls -la ~/documusic/outputs/ | head -10"))

# 3. Check if read-only
print("\n=== WRITE TEST (host) ===")
print(run(ssh, "touch ~/documusic/outputs/test_write && echo 'WRITE OK' && rm ~/documusic/outputs/test_write"))

# 4. Check container status
print("\n=== CONTAINER STATUS ===")
print(run(ssh, "docker ps -a --filter name=documusic_backend --format '{{.Status}}'"))

# 5. Check mount inside container
print("\n=== CONTAINER MOUNT ===")
print(run(ssh, "docker exec documusic_backend mount | grep outputs"))

# 6. Write test inside container
print("\n=== WRITE TEST (container) ===")
print(run(ssh, "docker exec documusic_backend bash -c 'touch /app/outputs/test_write && echo WRITE_OK && rm /app/outputs/test_write' 2>&1"))

# 7. Check inode usage
print("\n=== INODE USAGE ===")
print(run(ssh, "df -i /home/pepe/documusic"))

# 8. Check dmesg for filesystem errors
print("\n=== DMESG ERRORS ===")
print(run(ssh, "dmesg | tail -20 2>/dev/null || echo 'no dmesg access'"))

ssh.close()
