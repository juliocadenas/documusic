import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

sftp = client.open_sftp()
for filename in ['/opt/YuE/inference/vocoder.py', '/opt/YuE/inference/infer.py']:
    try:
        with sftp.file(filename, 'r') as f:
            print(f"--- {filename} ---")
            lines = f.readlines()
            for i, line in enumerate(lines):
                if 'build_codec_model' in line or 'feature_extractor' in line or 'VocosDecoder' in line or 'vocal_decoder_path' in line:
                    print(f"{i}: {line.strip()}")
    except Exception as e:
        print(e)

sftp.close()
client.close()
