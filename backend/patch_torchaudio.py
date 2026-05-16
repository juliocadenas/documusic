"""Patch torchaudio _check_cuda_version to skip CUDA version mismatch check.
This is needed because PyTorch nightly (cu130) may not match torchaudio (cu128).
"""
import os

TA_UTILS = "/usr/local/lib/python3.10/dist-packages/torchaudio/_extension/utils.py"

if not os.path.exists(TA_UTILS):
    print(f"File not found: {TA_UTILS}")
    exit(0)

# Check if already patched
with open(TA_UTILS) as f:
    content = f.read()

if "_check_cuda_version():" in content and "pass" in content:
    # Check if the function body is just "pass" (already patched)
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'def _check_cuda_version(' in line:
            # Check next non-empty line
            for j in range(i+1, min(i+5, len(lines))):
                if lines[j].strip() and lines[j].strip() != '':
                    if lines[j].strip() == 'pass':
                        print("Already patched")
                        exit(0)
                    break
            break

# Apply patch: replace _check_cuda_version function body with pass
new_lines = []
in_func = False
func_indent = 0

for line in lines:
    if line.strip().startswith('def _check_cuda_version(') and not in_func:
        in_func = True
        func_indent = len(line) - len(line.lstrip())
        new_lines.append(line)
        new_lines.append(' ' * (func_indent + 4) + 'pass\n')
        continue
    if in_func:
        if line.strip() == '' or (len(line) - len(line.lstrip()) > func_indent):
            continue  # skip function body
        else:
            in_func = False
            new_lines.append(line)
    else:
        new_lines.append(line)

with open(TA_UTILS, 'w') as f:
    f.writelines(new_lines)

print(f"Patched {TA_UTILS}")
