"""Check if vtrack.wav is actually silent and analyze the audio content."""
import paramiko

def run(ssh, cmd, timeout=30):
    print(f"  → {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip(): print(f"  ← {out.strip()[:2000]}")
    if err.strip(): print(f"  ⚠ {err.strip()[:500]}")
    return out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.103.141.33", username="pepe", password="pepe1234")

# 1. Compare vtrack and itrack WAV files (md5)
print("=== MD5 of vtrack vs itrack ===")
run(ssh, "docker exec documusic_backend md5sum /app/outputs/44d655f7/v1/recons/*vtrack*.wav /app/outputs/44d655f7/v1/recons/*itrack*.wav")

# 2. Check RMS levels of vtrack vs itrack using ffmpeg
print("\n=== Volume analysis (vtrack) ===")
run(ssh, "docker exec documusic_backend ffmpeg -i /app/outputs/44d655f7/v1/recons/*vtrack*.wav -af 'volumedetect' -f null /dev/null 2>&1 | grep -i 'mean_volume\\|max_volume'")

print("\n=== Volume analysis (itrack) ===")
run(ssh, "docker exec documusic_backend ffmpeg -i /app/outputs/44d655f7/v1/recons/*itrack*.wav -af 'volumedetect' -f null /dev/null 2>&1 | grep -i 'mean_volume\\|max_volume'")

# 3. Check the numpy arrays - are they all zeros/same values?
print("\n=== Numpy array analysis ===")
run(ssh, """docker exec documusic_backend python3 -c "
import numpy as np
vt = np.load('/app/outputs/44d655f7/v1/stage2/country-banjo-bass-male-singing-full-vocal-warm-vocal-vocal-raw_tp0@93_T1@0_rp1@2_maxtk1500_63c496c3-c6bf-4fa4-b988-3291f6da15fb_vtrack.npy')
it = np.load('/app/outputs/44d655f7/v1/stage2/country-banjo-bass-male-singing-full-vocal-warm-vocal-vocal-raw_tp0@93_T1@0_rp1@2_maxtk1500_63c496c3-c6bf-4fa4-b988-3291f6da15fb_itrack.npy')
print(f'vtrack shape: {vt.shape}, dtype: {vt.dtype}')
print(f'itrack shape: {it.shape}, dtype: {it.dtype}')
print(f'vtrack unique values: {len(np.unique(vt))}, min: {vt.min()}, max: {vt.max()}')
print(f'itrack unique values: {len(np.unique(it))}, min: {it.min()}, max: {it.max()}')
print(f'vtrack[:20]: {vt[:20]}')
print(f'itrack[:20]: {it[:20]}')
print(f'Are they identical? {np.array_equal(vt, it)}')
# Check if vtrack is mostly one value (silence token)
from collections import Counter
vt_counts = Counter(vt.flatten())
print(f'vtrack most common: {vt_counts.most_common(5)}')
it_counts = Counter(it.flatten())
print(f'itrack most common: {it_counts.most_common(5)}')
"
""", timeout=30)

# 4. Read the infer.py to understand how vocals work
print("\n=== Infer.py vocal handling code ===")
run(ssh, "grep -n 'vtrack\\|itrack\\|rearrange\\|codec_ids\\|vocal\\|split\\|cot\\|think' /opt/YuE/inference/infer.py | head -40")

# 5. Check the actual infer.py code around the output generation
print("\n=== Infer.py lines 270-320 (output handling) ===")
run(ssh, "sed -n '260,330p' /opt/YuE/inference/infer.py")

ssh.close()
print("\n🏁 Analysis complete!")
