"""Final check on job dbee957c with audio analysis."""
import paramiko
import json

def run(ssh, cmd, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode().strip()

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.103.141.33", username="pepe", password="pepe1234")

job_id = "dbee957c"
status_raw = run(ssh, f"curl -s http://localhost:8000/api/job/{job_id}")
try:
    job = json.loads(status_raw)
    print(f"Status: {job.get('status')}")
    print(f"Audio URL: {job.get('audio_url')}")
    print(f"Error: {job.get('error')}")
    logs = job.get('logs', [])
    print(f"\nLast 10 logs:")
    for log in logs[-10:]:
        print(f"  {log}")
    
    if job.get('status') == 'done' and job.get('audio_url'):
        # Check mastered file volume
        print("\n=== MASTERED AUDIO ANALYSIS ===")
        vol = run(ssh, 'docker exec documusic_backend ffmpeg -i /app/outputs/dbee957c.mp3 -af "volumedetect" -f null /dev/null 2>&1')
        for line in vol.split('\n'):
            if 'mean_volume' in line or 'max_volume' in line:
                print(line.strip())
        
        # Check file info
        info = run(ssh, 'docker exec documusic_backend ffprobe -v quiet -print_format json -show_format /app/outputs/dbee957c.mp3')
        try:
            f = json.loads(info).get('format', {})
            print(f"\nDuration: {f.get('duration')}s")
            print(f"Size: {int(f.get('size', 0)) / 1024:.1f} KB")
        except:
            pass
        
        print(f"\n🎧 Listen: http://100.103.141.33:8000/api/outputs/dbee957c.mp3")
except Exception as e:
    print(f"Error: {e}")
    print(status_raw[:500])

gpu = run(ssh, "nvidia-smi --query-gpu=memory.used --format=csv,noheader")
print(f"\nGPU: {gpu} MiB")

ssh.close()
