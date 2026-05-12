import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

try:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=15)
    
    script = """#!/bin/bash
cd /opt/YuE/inference
echo "[verse]\\nTest\\n[chorus]\\nTest" > /tmp/lyrics.txt
echo "Pop Rock" > /tmp/style.txt
export PYTHONPATH=.:xcodec_mini_infer:xcodec_mini_infer/models:vocos
export ATTENTION_IMPLEMENTATION=sdpa
export USE_FLASH_ATTN=0
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export PYTHONUNBUFFERED=1

python3 infer.py \\
    --stage1_model /app/models/YuE-s1 \\
    --stage2_model /app/models/YuE-s2 \\
    --genre_txt /tmp/style.txt \\
    --lyrics_txt /tmp/lyrics.txt \\
    --output_dir /tmp/testout \\
    --cuda_idx 0 \\
    --max_new_tokens 2000 \\
    --run_n_segments 2 \\
    --basic_model_config xcodec_mini_infer/final_ckpt/config.yaml \\
    --resume_path xcodec_mini_infer/final_ckpt/ckpt_00360000.pth 2>&1
"""
    
    sftp = c.open_sftp()
    with sftp.file('/tmp/run_test.sh', 'w') as f:
        f.write(script)
    sftp.close()
    
    stdin, stdout, stderr = c.exec_command(f"echo {PASS} | sudo -S docker cp /tmp/run_test.sh documusic_backend:/tmp/run_test.sh")
    stdout.read()
    
    stdin, stdout, stderr = c.exec_command(f"echo {PASS} | sudo -S docker exec documusic_backend bash /tmp/run_test.sh")
    out = stdout.read().decode('utf-8', errors='replace')
    
    with open("c:\\Users\\julio\\Documents\\Proyectos\\documusic\\test_output.txt", "w", encoding="utf-8") as f:
        f.write(out)
        
    print("Test finished. Output saved to test_output.txt")
except Exception as e:
    print(f"Error: {e}")
finally:
    c.close()
