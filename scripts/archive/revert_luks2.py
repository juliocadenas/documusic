import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

script = """
set -e
echo "1. Restaurando crypttab a su estado original..."
sed -i 's|/etc/luks-keys/root.key luks|none luks|g' /etc/crypttab

echo "2. Limpiando el registro del USB virtual en el sistema de arranque..."
sed -i '/KEYFILE_PATTERN/d' /etc/cryptsetup-initramfs/conf-hook || true

echo "3. Destruyendo el archivo de clave física..."
rm -rf /etc/luks-keys

echo "4. Recompilando el núcleo de arranque (30 segundos)..."
update-initramfs -u

echo "¡El servidor ha vuelto a su seguridad original!"
"""

stdin, stdout, stderr = client.exec_command("echo pepe1234 | sudo -S bash -c '{}'".format(script.replace("'", "'\\''")))
print("--- stdout ---")
print(stdout.read().decode('utf-8'))
print("--- stderr ---")
print(stderr.read().decode('utf-8'))

client.close()
