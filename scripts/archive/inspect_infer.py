import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=15)

# Leer infer.py actual del contenedor
stdin, stdout, _ = c.exec_command("docker exec documusic_backend cat /opt/YuE/inference/infer.py")
infer_code = stdout.read().decode("utf-8", errors="replace")

# Escribir a disco para inspeccion
with open("infer_actual.py", "w", encoding="utf-8") as f:
    f.write(infer_code)

print(f"infer.py descargado: {len(infer_code)} chars, {infer_code.count(chr(10))} lineas")

# Buscar la linea problematica
for i, line in enumerate(infer_code.split("\n"), 1):
    if "model_stage2" in line and (".to(" in line or "model.cpu" in line or "offload" in line.lower()):
        print(f"  L{i}: {line.rstrip()}")
    if "del model" in line or "torch.cuda.empty_cache" in line:
        print(f"  L{i}: {line.rstrip()}")

c.close()
