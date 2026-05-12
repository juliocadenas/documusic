import paramiko
import sys

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

try:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=15)
    stdin, stdout, stderr = c.exec_command('docker logs --tail 50 documusic_backend')
    out = stdout.read()
    err = stderr.read()
    
    # Escribir en un archivo para que lo podamos leer sin que crashee la terminal de Windows
    with open("c:\\Users\\julio\\Documents\\Proyectos\\documusic\\server_logs.txt", "wb") as f:
        f.write(out)
        f.write(b"\n--- STDERR ---\n")
        f.write(err)
        
    print("Logs saved to server_logs.txt")
except Exception as e:
    print(f"Error: {e}")
finally:
    c.close()
