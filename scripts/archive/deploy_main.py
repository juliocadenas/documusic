import paramiko
import os

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=15)

def run(cmd):
    stdin, stdout, stderr = c.exec_command(f"echo {PASS} | sudo -S bash -c '{cmd}'")
    return stdout.read().decode('utf-8', errors='replace'), stderr.read().decode('utf-8', errors='replace')

# Read local file
with open('c:\\Users\\julio\\Documents\\Proyectos\\documusic\\main_madrid.py', 'r') as f:
    code = f.read()

# Write to remote /tmp/main.py
sftp = c.open_sftp()
with sftp.file('/tmp/main_madrid.py', 'w') as f:
    f.write(code)
sftp.close()

# Copy to container and restart
print("Copying to container...")
out, err = run("docker cp /tmp/main_madrid.py documusic_backend:/app/main.py")
if err: print("Error copying:", err)

print("Restarting container...")
out, err = run("docker restart documusic_backend")
print("Done!")
c.close()
