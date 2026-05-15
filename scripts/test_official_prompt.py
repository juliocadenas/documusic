"""Test YuE with the OFFICIAL example prompt to see if vocals work at all."""
import paramiko, time

def run(ssh, cmd, timeout=120):
    print(f"  → {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    code = stdout.channel.recv_exit_status()
    if out.strip(): print(f"  ← {out.strip()[:2000]}")
    if err.strip(): print(f"  ⚠ {err.strip()[:500]}")
    return code, out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.103.141.33", username="pepe", password="pepe1234")

# 1. Create test files with official example prompt
print("=== Creating test prompt files ===")
run(ssh, """docker exec documusic_backend bash -c 'cat > /tmp/test_genre.txt << "EOF"
inspiring female uplifting pop airy vocal electronic bright vocal vocal
EOF
'""")

run(ssh, """docker exec documusic_backend bash -c 'cat > /tmp/test_lyrics.txt << "EOF"
[verse]
Staring at the sunset, colors paint the sky
Thoughts of you keep swirling, cant deny
I know I let you down, I made mistakes
But Im here to mend the heart I didnt break

[chorus]
Every road you take, Ill be one step behind
Every dream you chase, Im reaching for the light
You cant fight this feeling now
I wont back down
You know you cant deny it now
I wont back down
EOF
'""")

# 2. Verify files
print("\n=== Verify test files ===")
run(ssh, "docker exec documusic_backend cat /tmp/test_genre.txt")
run(ssh, "docker exec documusic_backend cat /tmp/test_lyrics.txt")

# 3. Run YuE directly with official example (8-bit, run_n_segments=2)
print("\n=== Running YuE with official example prompt ===")
print("  (This will take several minutes...)")

cmd = """docker exec documusic_backend bash -c 'cd /opt/YuE/inference && YUE_USE_8BIT=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True python3 infer.py \
  --stage1_model /app/models/YuE-s1 \
  --stage2_model /app/models/YuE-s2 \
  --genre_txt /tmp/test_genre.txt \
  --lyrics_txt /tmp/test_lyrics.txt \
  --output_dir /app/outputs/test_official \
  --cuda_idx 0 \
  --max_new_tokens 1500 \
  --run_n_segments 2 \
  --stage2_batch_size 1 \
  --seed 42 \
  --rescale 2>&1'"""

code, out, err = run(ssh, cmd, timeout=600)

print(f"\n=== Exit code: {code} ===")

# 4. Check output
print("\n=== Output files ===")
run(ssh, "docker exec documusic_backend find /app/outputs/test_official/ -name '*.wav' -exec ls -la {} \\; 2>/dev/null")

# 5. Check volume levels
print("\n=== Volume levels ===")
run(ssh, """docker exec documusic_backend bash -c 'for f in $(find /app/outputs/test_official/ -name "*vtrack*.wav" -type f | head -1); do echo "vtrack: $f"; ffmpeg -i "$f" -af volumedetect -f null /dev/null 2>&1 | grep -i "mean_volume\\|max_volume"; done'""")
run(ssh, """docker exec documusic_backend bash -c 'for f in $(find /app/outputs/test_official/ -name "*itrack*.wav" -type f | head -1); do echo "itrack: $f"; ffmpeg -i "$f" -af volumedetect -f null /dev/null 2>&1 | grep -i "mean_volume\\|max_volume"; done'""")

# 6. Copy mixed output to accessible location
print("\n=== Mixed output ===")
run(ssh, "docker exec documusic_backend find /app/outputs/test_official/ -name '*mixed*' -name '*.wav' -exec ls -la {} \\;")

ssh.close()
print("\n🏁 Test complete!")
