import re

with open('infer_current.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Quitar 8-bit de stage 1 y cambiar a sdpa
code = code.replace('load_in_8bit=True,', '')
code = code.replace('attn_implementation="eager"', 'attn_implementation="sdpa"')
code = code.replace('# model.to(device) [DISABLED FOR 8BIT]', 'model.to(device)')

with open('infer_current_fixed.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Fix local completado")
