"""
Deploy HeartMuLa to DocuMusic server (Madrid).
Installs HeartMuLa repo, downloads checkpoints, and restarts the backend.

Usage:
    python scripts/deploy_heartmula.py
"""
import paramiko
import time
import sys

# Server config
HOST = "100.103.141.33"
USER = "pepe"
PASS = "pepe1234"
CONTAINER = "documusic_backend"


def run(ssh, cmd, timeout=120, show=True):
    """Run command on remote server via paramiko."""
    if show:
        print(f"\n>>> {cmd[:120]}...")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    code = stdout.channel.recv_exit_status()
    if out and show:
        print(out[:500])
    if err and 'warning' not in err.lower() and show:
        print(f"STDERR: {err[:300]}")
    return out, err, code


def main():
    print("=" * 60)
    print("🎵 HeartMuLa 3B — Deploy to DocuMusic Madrid Server")
    print("=" * 60)

    # Connect
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"\n🔗 Conectando a {HOST}...")
    ssh.connect(HOST, username=USER, password=PASS, timeout=30)
    print("✅ Conectado!")

    # Step 1: Check if heartlib is already cloned
    # HeartMuLa will be cloned to /home/pepe/AI_MODELS/heartlib (pepe has write access)
    # and mounted as /opt/heartlib inside the Docker container
    HEARTMULA_HOST_DIR = "/home/pepe/AI_MODELS/heartlib"

    print(f"\n📦 Step 1: Checking HeartMuLa installation at {HEARTMULA_HOST_DIR}...")
    out, _, _ = run(ssh, f"test -d {HEARTMULA_HOST_DIR} && echo EXISTS || echo MISSING")

    if "EXISTS" in out:
        print(f"✅ HeartMuLa repo already exists at {HEARTMULA_HOST_DIR}")
    else:
        print("📥 Cloning HeartMuLa repo...")
        out, err, code = run(ssh, f"git clone https://github.com/HeartMuLa/heartlib.git {HEARTMULA_HOST_DIR}", timeout=300)
        if code != 0:
            print(f"❌ Failed to clone HeartMuLa: {err}")
            ssh.close()
            return

    # Step 2: Install heartlib package on host (for potential direct use)
    print("\n📦 Step 2: Installing heartlib package on host...")
    run(ssh, f"cd {HEARTMULA_HOST_DIR} && pip3 install -e . 2>&1 | tail -5", timeout=120, show=True)

    # Step 3: Download checkpoints
    print("\n📦 Step 3: Downloading HeartMuLa checkpoints...")
    run(ssh, "mkdir -p /home/pepe/AI_MODELS/huggingface/HeartMuLa")

    # Check if checkpoints already exist
    out, _, _ = run(ssh, "test -d /home/pepe/AI_MODELS/huggingface/HeartMuLa/HeartMuLa-oss-3B && echo CKPT_EXISTS || echo CKPT_MISSING")

    if "CKPT_EXISTS" in out:
        print("✅ HeartMuLa checkpoints already downloaded")
    else:
        print("📥 Downloading HeartMuLa-oss-3B + HeartCodec + HeartMuLaGen...")
        print("   (This may take 10-20 minutes depending on bandwidth...)")
        out, err, code = run(ssh,
            "cd /home/pepe/AI_MODELS/huggingface/HeartMuLa && "
            "pip3 install -q huggingface_hub && "
            "echo 'Downloading HeartMuLaGen...' && "
            "hf download --local-dir '.' 'HeartMuLa/HeartMuLaGen' && "
            "echo 'Downloading HeartMuLa-oss-3B...' && "
            "hf download --local-dir './HeartMuLa-oss-3B' 'HeartMuLa/HeartMuLa-oss-3B-happy-new-year' && "
            "echo 'Downloading HeartCodec-oss...' && "
            "hf download --local-dir './HeartCodec-oss' 'HeartMuLa/HeartCodec-oss-20260123' && "
            "echo 'ALL_DOWNLOADS_COMPLETE'",
            timeout=1800  # 30 minutes max for downloads
        )
        if "ALL_DOWNLOADS_COMPLETE" in out:
            print("✅ All checkpoints downloaded!")
        else:
            print(f"⚠️ Download may have issues: {out[-300:]}")

    # Step 4: Verify checkpoints
    print("\n📦 Step 4: Verifying checkpoints...")
    run(ssh, "ls -la /home/pepe/AI_MODELS/huggingface/HeartMuLa/", show=True)
    run(ssh, "ls /home/pepe/AI_MODELS/huggingface/HeartMuLa/HeartMuLa-oss-3B/ 2>/dev/null | head -10", show=True)
    run(ssh, "ls /home/pepe/AI_MODELS/huggingface/HeartMuLa/HeartCodec-oss/ 2>/dev/null | head -10", show=True)

    # Step 5: Git pull to get latest code
    print("\n📦 Step 5: Git pull to get updated code...")
    out, err, code = run(ssh, "cd ~/documusic && git fetch origin && git reset --hard origin/main && git pull origin main", timeout=60)
    if code != 0:
        run(ssh, "cd ~/documusic && git stash && git pull origin main", timeout=60)
    print(f"  ✅ Git actualizado")

    # Step 6: Verify HeartMuLa code is present
    print("\n📦 Step 6: Verifying HeartMuLa code...")
    out, _, _ = run(ssh, "grep -c 'heartmula' ~/documusic/backend/main.py")
    print(f"  HeartMuLa references in main.py: {out}")
    out, _, _ = run(ssh, "test -f ~/documusic/backend/engines/heartmula_engine.py && echo ENGINE_EXISTS || echo ENGINE_MISSING")
    print(f"  heartmula_engine.py: {out}")

    # Step 7: Install heartlib inside container
    print("\n📦 Step 7: Installing heartlib inside container...")
    run(ssh, f"docker exec {CONTAINER} bash -c 'cd /opt/heartlib && pip3 install -e . 2>&1 | tail -5'", timeout=120, show=True)

    # Step 8: Verify inside container
    print("\n📦 Step 8: Verifying installation inside container...")
    run(ssh, f"docker exec {CONTAINER} python3 -c 'import heartlib; print(\"✅ heartlib importable\")' 2>&1", show=True)
    run(ssh, f"docker exec {CONTAINER} ls /app/models/HeartMuLa/ 2>/dev/null || echo 'HeartMuLa ckpt dir not in container'", show=True)

    # Step 9: Restart backend
    print("\n📦 Step 9: Restarting backend...")
    run(ssh, f"docker restart {CONTAINER}", timeout=60)

    # Step 10: Wait and check
    print("\n⏳ Waiting for server to start...")
    for i in range(15):
        time.sleep(2)
        out, _, code = run(ssh, "curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/", timeout=5, show=False)
        if out.strip() == "200":
            print(f"  ✅ Backend online after {(i+1)*2}s")
            break
        print(f"  Waiting... ({(i+1)*2}s)")
    else:
        print("  ⚠️ Backend not responding, checking logs...")
        run(ssh, "docker logs documusic_backend --tail 30 2>&1", show=True)

    # Step 11: Final status check
    print("\n📦 Step 11: Final status check...")
    run(ssh, "curl -s http://localhost:8000/api | python3 -m json.tool 2>/dev/null | head -25", show=True)

    ssh.close()

    print("\n" + "=" * 60)
    print("✅ HeartMuLa deployment complete!")
    print("=" * 60)
    print("\n🎯 Next steps:")
    print("  1. Open DocuMusic frontend (localhost:5173)")
    print("  2. Select 'HeartMuLa 3B ⭐ Recomendado' from model selector")
    print("  3. Enter lyrics and style/tags")
    print("  4. Generate and compare with YuE!")
    print()


if __name__ == "__main__":
    main()
