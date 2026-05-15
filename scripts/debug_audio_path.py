"""Debug audio path - check what files exist and their volumes."""
import paramiko

def run(ssh, cmd, timeout=15):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return out + (f"\nSTDERR: {err}" if err else "")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.103.141.33", username="pepe", password="pepe1234")

# List all files in output directory
print("=== FILES IN OUTPUT DIR ===")
files = run(ssh, "docker exec documusic_backend find /app/outputs/ceae571b -type f")
print(files)

# Check the mixed WAV file
print("\n=== MIXED WAV ===")
mixed = run(ssh, "docker exec documusic_backend find /app/outputs/ceae571b -name '*mixed*' -type f")
print(f"Mixed files: {mixed}")

if mixed:
    first_mixed = mixed.split('\n')[0]
    info = run(ssh, f'docker exec documusic_backend ffprobe -v quiet -print_format json -show_format -show_streams "{first_mixed}"')
    print(f"Mixed info: {info[:500]}")

    # Volume of mixed
    vol = run(ssh, f'docker exec documusic_backend ffmpeg -i "{first_mixed}" -af "volumedetect" -f null /dev/null 2>&1', timeout=30)
    for line in vol.split('\n'):
        if 'mean_volume' in line or 'max_volume' in line:
            print(line.strip())

# Check the stems
print("\n=== STEMS ===")
stems = run(ssh, "docker exec documusic_backend ls -la /app/outputs/ceae571b/v1/vocoder/stems/ 2>/dev/null")
print(stems)

# Volume of vtrack
print("\n=== VTRACK VOLUME ===")
vol = run(ssh, 'docker exec documusic_backend ffmpeg -i /app/outputs/ceae571b/v1/vocoder/stems/vtrack.wav -af "volumedetect" -f null /dev/null 2>&1', timeout=30)
for line in vol.split('\n'):
    if 'mean_volume' in line or 'max_volume' in line:
        print(line.strip())

# Volume of itrack
print("\n=== ITRACK VOLUME ===")
vol = run(ssh, 'docker exec documusic_backend ffmpeg -i /app/outputs/ceae571b/v1/vocoder/stems/itrack.wav -af "volumedetect" -f null /dev/null 2>&1', timeout=30)
for line in vol.split('\n'):
    if 'mean_volume' in line or 'max_volume' in line:
        print(line.strip())

# Check the raw mp3
print("\n=== RAW MP3 ===")
raw = run(ssh, "docker exec documusic_backend ls -la /app/outputs/ceae571b_raw.mp3 2>/dev/null")
print(raw)

# Check what _finalize_audio found as source
print("\n=== ALL MP3/WAV IN OUTPUTS ===")
all_audio = run(ssh, "docker exec documusic_backend find /app/outputs/ceae571b -name '*.mp3' -o -name '*.wav' | head -20")
print(all_audio)

# Check the mix directory
print("\n=== MIX DIR ===")
mix_dir = run(ssh, "docker exec documusic_backend ls -la /app/outputs/ceae571b/v1/vocoder/mix/ 2>/dev/null")
print(mix_dir)

ssh.close()
