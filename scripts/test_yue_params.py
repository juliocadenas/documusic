"""
P1.2: Progressive parameter test for YuE on the server.
Tests different combinations of max_new_tokens and run_n_segments to find
the optimal balance between audio duration and VRAM usage.

Usage: python scripts/test_yue_params.py
"""
import paramiko
import time
import sys

HOST = "100.103.141.33"
USER = "pepe"
PASS = "pepe1234"

# Official YuE example prompt (proven to produce vocals)
OFFICIAL_GENRE = "inspiring female uplifting pop airy vocal electronic bright vocal vocal"
OFFICIAL_LYRICS = """[verse]
In the silence of the night, stars are shining bright
Every dream I hold inside, feels like taking flight
Through the darkness there's a spark, guiding me so far
I believe in who I am, I'm a shooting star

[chorus]
Rise above the clouds, let the music play
Nothing's gonna stop us on this beautiful day
Feel the rhythm in your heart, let it show you the way
We're unstoppable together, come what may

[verse]
Every step I take ahead, echoes in my mind
Leaving all the doubts behind, treasures I will find
With the wind beneath my wings, soaring ever high
Reaching for the rainbow, painting up the sky"""

# Test configurations: (name, max_new_tokens, run_n_segments)
TESTS = [
    ("T1_tok3000_seg1", 3000, 1),
    ("T2_tok3000_seg2", 3000, 2),
    ("T3_tok4500_seg1", 4500, 1),
    ("T4_tok4500_seg2", 4500, 2),
]


def run(ssh, cmd, timeout=30):
    """Execute command and return output."""
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return out, err


def check_gpu(ssh):
    """Get current GPU memory usage."""
    out, _ = run(ssh, "nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits")
    return out


def run_test(ssh, test_name, max_new_tokens, run_n_segments):
    """Run a single YuE inference test."""
    print(f"\n{'='*60}")
    print(f"🧪 TEST: {test_name}")
    print(f"   max_new_tokens={max_new_tokens}, run_n_segments={run_n_segments}")
    print(f"{'='*60}")

    # Check GPU is free
    gpu = check_gpu(ssh)
    print(f"   GPU before: {gpu} MiB")

    # Create test directory and files
    setup_cmd = f"""docker exec documusic_backend bash -c '
        mkdir -p /app/outputs/param_test/{test_name} &&
        cat > /app/outputs/param_test/{test_name}/genre.txt << "GENRE_EOF"
{OFFICIAL_GENRE}
GENRE_EOF
        cat > /app/outputs/param_test/{test_name}/lyrics.txt << "LYRICS_EOF"
{OFFICIAL_LYRICS}
LYRICS_EOF
        echo "Files created"
    '"""
    out, err = run(ssh, setup_cmd, timeout=15)
    print(f"   Setup: {out}")

    # Build inference command (16-bit: YUE_USE_8BIT=0)
    infer_cmd = f"""docker exec -d documusic_backend bash -c '
        cd /opt/YuE/inference && \
        export YUE_USE_8BIT=0 && \
        export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True && \
        export PYTHONPATH=/opt/YuE/inference:/opt/YuE/inference/xcodec_mini_infer:/opt/YuE/inference/xcodec_mini_infer/models:/opt/YuE/inference/vocos:\$PYTHONPATH && \
        python3 infer.py \
            --stage1_model /app/models/YuE-s1 \
            --stage2_model /app/models/YuE-s2 \
            --genre_txt /app/outputs/param_test/{test_name}/genre.txt \
            --lyrics_txt /app/outputs/param_test/{test_name}/lyrics.txt \
            --output_dir /app/outputs/param_test/{test_name} \
            --cuda_idx 0 \
            --max_new_tokens {max_new_tokens} \
            --run_n_segments {run_n_segments} \
            --stage2_batch_size 1 \
            --repetition_penalty 1.2 \
            --seed 42 \
            --vocal_decoder_path ./xcodec_mini_infer/decoders/decoder_131000.pth \
            --inst_decoder_path ./xcodec_mini_infer/decoders/decoder_151000.pth \
            --basic_model_config ./xcodec_mini_infer/final_ckpt/config.yaml \
            --resume_path ./xcodec_mini_infer/final_ckpt/ckpt_00360000.pth \
            --rescale \
            > /app/outputs/param_test/{test_name}/log.txt 2>&1 && \
        echo "SUCCESS" >> /app/outputs/param_test/{test_name}/log.txt || \
        echo "FAILED" >> /app/outputs/param_test/{test_name}/log.txt
    '"""

    out, err = run(ssh, infer_cmd, timeout=15)
    print(f"   Inference started in background")

    # Wait for completion (check every 30s)
    start_time = time.time()
    max_wait = 30 * 60  # 30 min max per test
    last_log_len = 0

    while time.time() - start_time < max_wait:
        time.sleep(30)
        elapsed = int(time.time() - start_time)

        # Check if process is still running
        out, _ = run(ssh, "docker exec documusic_backend ps aux | grep 'infer.py' | grep -v grep | wc -l", timeout=10)
        running = out.strip()

        # Check log
        log_out, _ = run(ssh, f"docker exec documusic_backend tail -5 /app/outputs/param_test/{test_name}/log.txt 2>/dev/null", timeout=10)

        # Check GPU
        gpu = check_gpu(ssh)

        print(f"   [{elapsed}s] GPU: {gpu} MiB | Running: {running} | Log: {log_out[-100:] if log_out else 'empty'}")

        if running == "0":
            # Process finished
            time.sleep(5)  # Wait for files to be written

            # Check result
            final_log, _ = run(ssh, f"docker exec documusic_backend tail -3 /app/outputs/param_test/{test_name}/log.txt 2>/dev/null")

            # Check for OOM
            oom_check, _ = run(ssh, f"docker exec documusic_backend grep -i 'out of memory\\|OOM\\|CUDA error' /app/outputs/param_test/{test_name}/log.txt 2>/dev/null | head -3")

            # Check output files
            files_out, _ = run(ssh, f"docker exec documusic_backend find /app/outputs/param_test/{test_name} -name '*.wav' -exec ls -la {{}} \\; 2>/dev/null | head -10")

            # Get duration
            dur_out, _ = run(ssh, f"""docker exec documusic_backend bash -c '
                MIXED=$(find /app/outputs/param_test/{test_name} -name "*mixed*" -name "*.wav" | head -1);
                if [ -n "$MIXED" ]; then
                    ffprobe -i "$MIXED" -show_entries format=duration -v quiet -of csv="p=0" 2>&1;
                else
                    echo "no_mixed_file";
                fi
            '""", timeout=15)

            # Get volume
            vol_out, _ = run(ssh, f"""docker exec documusic_backend bash -c '
                VTRACK=$(find /app/outputs/param_test/{test_name} -name "*vtrack*.wav" -path "*/recons/*" | head -1);
                if [ -n "$VTRACK" ]; then
                    ffmpeg -i "$VTRACK" -af volumedetect -f null /dev/null 2>&1 | grep -i "mean_volume\\|max_volume";
                else
                    echo "no_vtrack";
                fi
            '""", timeout=15)

            print(f"\n   📊 RESULTS for {test_name}:")
            print(f"   Status: {'✅ SUCCESS' if 'SUCCESS' in final_log else '❌ FAILED'}")
            if oom_check:
                print(f"   ⚠️  OOM: {oom_check}")
            print(f"   Duration: {dur_out}")
            print(f"   Vocal volume: {vol_out}")
            print(f"   Files: {files_out[:300]}")
            print(f"   GPU after: {check_gpu(ssh)} MiB")

            return {
                "name": test_name,
                "max_new_tokens": max_new_tokens,
                "run_n_segments": run_n_segments,
                "success": "SUCCESS" in final_log,
                "oom": bool(oom_check),
                "duration": dur_out,
                "vocal_volume": vol_out,
                "files": files_out,
            }

    print(f"   ⏰ TIMEOUT after {max_wait//60} minutes!")
    return {
        "name": test_name,
        "max_new_tokens": max_new_tokens,
        "run_n_segments": run_n_segments,
        "success": False,
        "oom": False,
        "duration": "timeout",
        "vocal_volume": "unknown",
        "files": "",
    }


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS)

    # Check server is up
    out, _ = run(ssh, "docker ps --format '{{.Names}} {{.Status}}' | grep documusic")
    print(f"🖥️  Server: {out}")

    gpu = check_gpu(ssh)
    print(f"🎮 GPU: {gpu} MiB")

    # Check if any previous test is still running
    out, _ = run(ssh, "docker exec documusic_backend ps aux | grep 'infer.py' | grep -v grep | wc -l")
    if out.strip() != "0":
        print("⚠️  YuE inference already running! Waiting for it to finish...")
        sys.exit(1)

    results = []

    # Run tests sequentially
    for test_name, max_tokens, n_segments in TESTS:
        result = run_test(ssh, test_name, max_tokens, n_segments)
        results.append(result)

        # If OOM, skip remaining tests with higher params
        if result["oom"]:
            print(f"\n⚠️  OOM detected! Skipping remaining higher-parameter tests.")
            break

        # Wait for GPU to cool down
        print(f"\n   Waiting 30s for GPU to stabilize...")
        time.sleep(30)

    # Summary
    print(f"\n{'='*60}")
    print("📋 SUMMARY")
    print(f"{'='*60}")
    for r in results:
        status = "✅" if r["success"] else "❌"
        oom = "OOM!" if r["oom"] else ""
        print(f"  {status} {r['name']}: tok={r['max_new_tokens']}, seg={r['run_n_segments']} | "
              f"dur={r['duration']} | {oom}")

    # Convert best result to MP3 for listening
    successful = [r for r in results if r["success"]]
    if successful:
        best = successful[-1]  # Last successful = highest params
        print(f"\n🎵 Converting best result ({best['name']}) to MP3...")
        convert_cmd = f"""docker exec documusic_backend bash -c '
            MIXED=$(find /app/outputs/param_test/{best["name"]} -name "*mixed*" -name "*.wav" -path "*/vocoder/mix/*" | head -1);
            if [ -n "$MIXED" ]; then
                ffmpeg -y -i "$MIXED" -codec:a libmp3lame -qscale:a 2 /app/outputs/param_test_best.mp3 2>&1 | tail -3;
                ls -la /app/outputs/param_test_best.mp3;
            else
                echo "No mixed file found";
            fi
        '"""
        out, _ = run(ssh, convert_cmd, timeout=30)
        print(f"   {out}")
        print(f"\n🎧 Listen at: http://{HOST}:8000/api/outputs/param_test_best.mp3")

    ssh.close()
    print("\n🏁 All tests complete!")


if __name__ == "__main__":
    main()
