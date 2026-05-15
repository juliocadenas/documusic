"""Test YuE with country style to compare with ACE-Step quality."""
import paramiko
import time
import json

def run(ssh, cmd, timeout=300):
    print(f"\n>>> {cmd}")
    try:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode('utf-8', errors='replace').strip()
        err = stderr.read().decode('utf-8', errors='replace').strip()
        if out:
            print(out[:3000])
        if err and len(err) < 1000:
            print(f"[STDERR] {err[:500]}")
        return out
    except Exception as e:
        print(f"[ERROR] {e}")
        return ""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.103.141.33', username='pepe', password='pepe1234')

# Test YuE generation via API
style = "American Country, dobro resonator, steel guitar slides, pedal steel guitar, male vocalist, warm baritone voice, Nashville sound, traditional country"
lyrics = """[Verse 1]
Driving down a dusty road, sunset painting sky of gold
Fences stretching mile on mile, this old land has got my soul
Daddy taught me how to ride, mama sang me lullabies
Country music in my blood, running deep as river tides

[Chorus]
Oh, this heart beats country time
Steel guitar and whiskey wine
Front porch swings and firefly lights
Home is where the music shines
Yeah, this heart beats country time

[Verse 2]
Grandpa's fiddle in the barn, weathered hands but fingers warm
Every note a memory, every song a family story
Crickets sing the backup choir, moon is hanging like a fire
Stars are watching from above, bless this life I truly love

[Chorus]
Oh, this heart beats country time
Steel guitar and whiskey wine
Front porch swings and firefly lights
Home is where the music shines
Yeah, this heart beats country time

[Bridge]
Some folks chase the city lights
But I'll take starry southern nights
Where the steel guitar cries out in pain
And every song sounds like sweet rain

[Chorus]
Oh, this heart beats country time
Steel guitar and whiskey wine
Front porch swings and firefly lights
Home is where the music shines
Yeah, this heart beats country time

[Outro]
Yeah, this heart beats country time
Mmm, country time"""

payload = json.dumps({
    "style_prompt": style,
    "lyrics": lyrics,
    "model": "yue",
    "num_variants": 1
})

print("=" * 60)
print("TESTING YuE WITH COUNTRY STYLE")
print("=" * 60)

# Send generation request
result = run(ssh, f'''curl -s -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{payload.replace("'", "'\"'\"'")}' ''')

print("\n" + "=" * 60)
print("RESPONSE")
print("=" * 60)
try:
    parsed = json.loads(result)
    job_id = parsed.get("job_id", "unknown")
    print(f"Job ID: {job_id}")
    print(f"Status: {parsed.get('status', 'unknown')}")
except:
    print(result[:500])

# Poll for completion
if 'job_id' in result:
    try:
        job_id = json.loads(result)["job_id"]
    except:
        job_id = "unknown"
    
    print(f"\nPolling job {job_id}...")
    for i in range(120):  # max 10 minutes
        time.sleep(5)
        status_out = run(ssh, f"curl -s http://localhost:8000/api/job/{job_id}", timeout=10)
        try:
            job = json.loads(status_out)
            st = job.get("status", "unknown")
            logs = job.get("logs", [])
            if logs:
                print(f"  [{i*5}s] Status: {st} | Last log: {logs[-1][:100]}")
            
            if st == "done":
                print(f"\nGENERATION COMPLETE!")
                print(f"Audio URL: {job.get('audio_url', 'N/A')}")
                print(f"Duration: {job.get('duration', 'N/A')}s")
                break
            elif st == "error":
                print(f"\nGENERATION FAILED: {job.get('error', 'Unknown')}")
                break
        except:
            pass

ssh.close()
print("\nDone.")
