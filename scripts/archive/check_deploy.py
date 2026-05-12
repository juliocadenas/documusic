"""Verifica el estado del deploy en el servidor Madrid."""
import paramiko
import time

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

def run(client, cmd, timeout=15):
    _, o, e = client.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    code = o.channel.recv_exit_status()
    return out, err, code

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=15)

# Check if build is still running
out, _, _ = run(c, "ps aux | grep 'docker.*build' | grep -v grep | head -3")
if out.strip():
    print("BUILD STILL RUNNING:")
    print(out)
else:
    print("No build process detected.")

# Check containers
out, _, _ = run(c, "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>&1")
print("\nCONTAINERS:")
print(out)

# If backend is running, check diagnostics
if "documusic" in out:
    out, _, _ = run(c, "curl -s http://localhost:8000/api/diagnostics 2>&1")
    print("\nDIAGNOSTICS:")
    print(out[:2000])

    out, _, _ = run(c, "docker logs documusic_backend --tail 15 2>&1")
    print("\nLOGS:")
    print(out)
else:
    # Check build logs
    out, _, _ = run(c, "cd /home/pepe/documusic && docker compose logs --tail 20 2>&1")
    print("\nCOMPOSE LOGS:")
    print(out)

c.close()
