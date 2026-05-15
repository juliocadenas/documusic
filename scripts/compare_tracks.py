"""Compare vtrack and itrack audio levels and check YuE prompt examples."""
import paramiko

def run(ssh, cmd, timeout=30):
    print(f"  → {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip(): print(f"  ← {out.strip()[:2000]}")
    if err.strip(): print(f"  ⚠ {err.strip()[:500]}")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.103.141.33", username="pepe", password="pepe1234")

# 1. Get exact paths for vtrack and itrack WAV files
print("=== Exact WAV paths ===")
run(ssh, "docker exec documusic_backend find /app/outputs/44d655f7/v1/recons/ -name '*.wav' -type f")

# 2. Check volume levels using ffmpeg (use exact paths)
print("\n=== vtrack volume ===")
run(ssh, """docker exec documusic_backend bash -c 'ffmpeg -i /app/outputs/44d655f7/v1/recons/country-banjo-bass-male-singing-full-vocal-warm-vocal-vocal-raw_tp0@93_T1@0_rp1@2_maxtk1500_63c496c3-c6bf-4fa4-b988-3291f6da15fb_vtrack.wav -af volumedetect -f null /dev/null 2>&1 | grep -i "mean_volume\\|max_volume"'""")

print("\n=== itrack volume ===")
run(ssh, """docker exec documusic_backend bash -c 'ffmpeg -i /app/outputs/44d655f7/v1/recons/country-banjo-bass-male-singing-full-vocal-warm-vocal-vocal-raw_tp0@93_T1@0_rp1@2_maxtk1500_63c496c3-c6bf-4fa4-b988-3291f6da15fb_itrack.wav -af volumedetect -f null /dev/null 2>&1 | grep -i "mean_volume\\|max_volume"'""")

# 3. Check YuE prompt examples
print("\n=== YuE prompt examples ===")
run(ssh, "docker exec documusic_backend ls /opt/YuE/prompt_egs/ 2>/dev/null")
run(ssh, "docker exec documusic_backend find /opt/YuE/prompt_egs/ -type f | head -10")

# 4. Read example genre/text files
print("\n=== Example genre tags ===")
run(ssh, "docker exec documusic_backend find /opt/YuE/prompt_egs/ -name '*.txt' -exec echo '--- {} ---' \\; -exec cat {} \\; 2>/dev/null | head -60")

# 5. Check the README for vocal generation tips
print("\n=== YuE README vocal section ===")
run(ssh, "docker exec documusic_backend grep -A5 -i 'vocal\\|sing\\|voice\\|genre.*tag' /opt/YuE/README.md | head -40")

# 6. Check the top_200_tags for vocal-related tags
print("\n=== Vocal-related tags from top_200 ===")
run(ssh, "docker exec documusic_backend python3 -c \"import json; tags=json.load(open('/opt/YuE/top_200_tags.json')); [print(t) for t in tags if any(w in t.lower() for w in ['vocal','sing','voice','male','female','rap','choir','hum'])]\"")

ssh.close()
print("\n🏁 Done!")
