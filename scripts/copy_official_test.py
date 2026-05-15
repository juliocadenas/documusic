"""Copy official test output to web-accessible location as MP3."""
import paramiko

def run(ssh, cmd, timeout=60):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip(): print(f"  ← {out.strip()[:2000]}")
    if err.strip(): print(f"  ⚠ {err.strip()[:500]}")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.103.141.33", username="pepe", password="pepe1234")

# Convert mixed.wav to mp3 and copy to outputs root
print("=== Converting mixed.wav to mp3 ===")
run(ssh, """docker exec documusic_backend bash -c 'cd /app/outputs/test_official && \
    MIXED=$(find . -name "*mixed.wav" -path "*/vocoder/mix/*" | head -1) && \
    echo "Found: $MIXED" && \
    ffmpeg -y -i "$MIXED" -codec:a libmp3lame -qscale:a 2 /app/outputs/test_official_mixed.mp3 2>&1 | tail -5 && \
    ls -la /app/outputs/test_official_mixed.mp3'""")

# Also convert vtrack and itrack separately
print("\n=== Converting vtrack to mp3 ===")
run(ssh, """docker exec documusic_backend bash -c 'cd /app/outputs/test_official && \
    VTRACK=$(find . -name "*vtrack.wav" -path "*/recons/*" | head -1) && \
    echo "Found: $VTRACK" && \
    ffmpeg -y -i "$VTRACK" -codec:a libmp3lame -qscale:a 2 /app/outputs/test_official_vtrack.mp3 2>&1 | tail -3 && \
    ls -la /app/outputs/test_official_vtrack.mp3'""")

print("\n=== Converting itrack to mp3 ===")
run(ssh, """docker exec documusic_backend bash -c 'cd /app/outputs/test_official && \
    ITRACK=$(find . -name "*itrack.wav" -path "*/recons/*" | head -1) && \
    echo "Found: $ITRACK" && \
    ffmpeg -y -i "$ITRACK" -codec:a libmp3lame -qscale:a 2 /app/outputs/test_official_itrack.mp3 2>&1 | tail -3 && \
    ls -la /app/outputs/test_official_itrack.mp3'""")

# Get duration of mixed output
print("\n=== Duration ===")
run(ssh, """docker exec documusic_backend ffprobe -i /app/outputs/test_official_mixed.mp3 -show_entries format=duration -v quiet -of csv="p=0" 2>&1""")

ssh.close()
print("\n🏁 Done! Files should be at:")
print("  http://100.103.141.33:8000/api/outputs/test_official_mixed.mp3")
print("  http://100.103.141.33:8000/api/outputs/test_official_vtrack.mp3")
print("  http://100.103.141.33:8000/api/outputs/test_official_itrack.mp3")
