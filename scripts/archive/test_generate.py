"""Prueba la generacion de la cancion en el servidor Madrid."""
import paramiko
import json
import time

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

LYRICS = """[verse]
Despierto en la madrugada, la consola me hablo
Otra linea de codigo que el sistema rechazo
Pero no voy a rendirme, tengo el poder de mi lado
Voy a domar a esta maquina hasta el ultimo centigrado.

[chorus]
Vamos a hacer que cante con un flow artificial!
Sube la guitarra, esto es nivel industrial!
No importa lo que cueste, no hay marcha atras!
Que retumbe el servidor, un poco de rock audaz!"""

STYLE = "Pop Rock, Melodic Male, highly expressive singing, clear pronunciation, harmonious, Energetic, passionate, Electric guitar, heavy drums, modern bass, Fast tempo"

def run(client, cmd, timeout=30):
    _, o, e = client.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    code = o.channel.recv_exit_status()
    return out, err, code

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=15)

# Write the payload to a temp file on the server to avoid shell escaping issues
payload = json.dumps({"lyrics": LYRICS, "style_prompt": STYLE, "model": "yue"})
escaped_payload = payload.replace("'", "'\\''")

# Use a heredoc approach to avoid escaping issues
cmd = "curl -s -X POST http://localhost:8000/api/generate -H 'Content-Type: application/json' -d @- << 'JSONEOF'\n" + payload + "\nJSONEOF"
print("Enviando peticion de generacion...")

out, err, code = run(c, cmd, timeout=30)
print(f"Response [{code}]: {out[:500]}")

# Extract job_id
try:
    data = json.loads(out)
    job_id = data.get("job_id")
    model_status = data.get("model_status")
    print(f"\nJob ID: {job_id}")
    print(f"Model Status: {model_status}")

    if job_id and model_status == "generating":
        print("\nEsperando generacion (polling cada 10s)...")
        for i in range(60):  # Max 10 minutes
            time.sleep(10)
            out, err, code = run(c, "curl -s http://localhost:8000/api/job/" + job_id + " 2>&1", timeout=15)
            try:
                job_data = json.loads(out)
                status = job_data.get("status", "unknown")
                logs = job_data.get("logs", [])
                print(f"\n  [{i*10}s] Status: {status} | Logs: {len(logs)} lineas")

                # Show last 3 logs
                if logs:
                    for log in logs[-3:]:
                        print(f"    > {log[:150]}")

                if status == "done":
                    audio_url = job_data.get("audio_url", "")
                    print(f"\n  === CANCION GENERADA! ===")
                    print(f"  Audio URL: http://{HOST}:8000{audio_url}")
                    break
                elif status == "error":
                    error = job_data.get("error", "Unknown error")
                    error_detail = job_data.get("error_detail", "")
                    print(f"\n  ERROR: {error}")
                    if error_detail:
                        print(f"  Detalle: {error_detail[:500]}")
                    print("\n  LOGS COMPLETOS:")
                    for log in logs:
                        print(f"    > {log[:200]}")
                    break
            except json.JSONDecodeError:
                print(f"  Raw: {out[:200]}")
    elif model_status == "demo":
        print("  Usando audio demo (modelos no disponibles)")
except json.JSONDecodeError as e:
    print(f"Error parsing response: {e}")
    print(f"Raw output: {out[:500]}")

c.close()
print("\nDone.")
