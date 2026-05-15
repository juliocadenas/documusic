"""Analyze the completed job output audio."""
import paramiko
import json

def run(ssh, cmd, timeout=15):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode().strip()

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.103.141.33", username="pepe", password="pepe1234")

# Check mastered file metrics
print("=== MASTERED FILE (ceae571b.mp3) ===")
metrics = run(ssh, 'docker exec documusic_backend ffprobe -v quiet -print_format json -show_format -show_streams /app/outputs/ceae571b.mp3')
try:
    info = json.loads(metrics)
    fmt = info.get('format', {})
    stream = info.get('streams', [{}])[0]
    print(f"Duration: {fmt.get('duration')}s")
    print(f"Size: {int(fmt.get('size', 0)) / 1024:.1f} KB")
    print(f"Bitrate: {int(fmt.get('bit_rate', 0)) / 1000:.0f} kbps")
    print(f"Sample rate: {stream.get('sample_rate')}")
    print(f"Channels: {stream.get('channels')}")
except Exception as e:
    print(f"Error parsing: {e}")
    print(metrics[:500])

# Check raw file metrics
print("\n=== RAW FILE (ceae571b_raw.mp3) ===")
raw_metrics = run(ssh, 'docker exec documusic_backend ffprobe -v quiet -print_format json -show_format -show_streams /app/outputs/ceae571b_raw.mp3')
try:
    info = json.loads(raw_metrics)
    fmt = info.get('format', {})
    stream = info.get('streams', [{}])[0]
    print(f"Duration: {fmt.get('duration')}s")
    print(f"Size: {int(fmt.get('size', 0)) / 1024:.1f} KB")
    print(f"Bitrate: {int(fmt.get('bit_rate', 0)) / 1000:.0f} kbps")
except Exception as e:
    print(f"Error: {e}")
    print(raw_metrics[:500])

# Volume analysis of mastered file
print("\n=== VOLUME ANALYSIS (mastered) ===")
vol = run(ssh, 'docker exec documusic_backend ffmpeg -i /app/outputs/ceae571b.mp3 -af "volumedetect" -f null /dev/null 2>&1', timeout=30)
# Parse mean_volume and max_volume
for line in vol.split('\n'):
    if 'mean_volume' in line or 'max_volume' in line:
        print(line.strip())

# Volume analysis of raw file
print("\n=== VOLUME ANALYSIS (raw) ===")
vol_raw = run(ssh, 'docker exec documusic_backend ffmpeg -i /app/outputs/ceae571b_raw.mp3 -af "volumedetect" -f null /dev/null 2>&1', timeout=30)
for line in vol_raw.split('\n'):
    if 'mean_volume' in line or 'max_volume' in line:
        print(line.strip())

# Also check the original wav files
print("\n=== VOCAL TRACK (vtrack.wav) ===")
vtrack = run(ssh, 'docker exec documusic_backend ffprobe -v quiet -print_format json -show_format /app/outputs/ceae571b/v1/vocoder/stems/vtrack.wav')
try:
    info = json.loads(vtrack)
    fmt = info.get('format', {})
    print(f"Duration: {fmt.get('duration')}s, Size: {int(fmt.get('size', 0)) / 1024:.1f} KB")
except:
    print(vtrack[:300])

print("\n=== INSTRUMENTAL TRACK (itrack.wav) ===")
itrack = run(ssh, 'docker exec documusic_backend ffprobe -v quiet -print_format json -show_format /app/outputs/ceae571b/v1/vocoder/stems/itrack.wav')
try:
    info = json.loads(itrack)
    fmt = info.get('format', {})
    print(f"Duration: {fmt.get('duration')}s, Size: {int(fmt.get('size', 0)) / 1024:.1f} KB")
except:
    print(itrack[:300])

# Volume of vtrack
print("\n=== VTRACK VOLUME ===")
vol_vt = run(ssh, 'docker exec documusic_backend ffmpeg -i /app/outputs/ceae571b/v1/vocoder/stems/vtrack.wav -af "volumedetect" -f null /dev/null 2>&1', timeout=30)
for line in vol_vt.split('\n'):
    if 'mean_volume' in line or 'max_volume' in line:
        print(line.strip())

# Volume of itrack
print("\n=== ITRACK VOLUME ===")
vol_it = run(ssh, 'docker exec documusic_backend ffmpeg -i /app/outputs/ceae571b/v1/vocoder/stems/itrack.wav -af "volumedetect" -f null /dev/null 2>&1', timeout=30)
for line in vol_it.split('\n'):
    if 'mean_volume' in line or 'max_volume' in line:
        print(line.strip())

ssh.close()
