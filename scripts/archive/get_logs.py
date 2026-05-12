import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=15)

# Guardar logs a archivo directamente
stdin, stdout, stderr = c.exec_command("docker logs documusic_backend --tail 150 2>&1")
raw = stdout.read()
with open("server_logs.txt", "wb") as f:
    f.write(raw)

# Buscar archivos generados
stdin2, stdout2, _ = c.exec_command(
    "docker exec documusic_backend find /app/outputs -type f 2>&1"
)
raw2 = stdout2.read()
with open("outputs_list.txt", "wb") as f:
    f.write(raw2)

c.close()
print("Logs guardados en server_logs.txt y outputs_list.txt")
