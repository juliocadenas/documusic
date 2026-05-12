import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

script = """
set -e
echo "1. Restaurando crypttab..."
sed -i 's|/etc/luks-keys/root.key luks|none luks|g' /etc/crypttab

echo "2. Limpiando hook de initramfs..."
sed -i '/KEYFILE_PATTERN/d' /etc/cryptsetup-initramfs/conf-hook || true

echo "3. Eliminando la llave del disco encriptado..."
if [ -f /etc/luks-keys/root.key ]; then
    cryptsetup luksRemoveKey /dev/sda3 /etc/luks-keys/root.key || true
    rm -rf /etc/luks-keys
fi

echo "4. Recompilando el kernel para restaurar la pantalla de contraseña visual..."
update-initramfs -u

echo "¡Restauración de seguridad completada con éxito!"
"""

stdin, stdout, stderr = client.exec_command("echo pepe1234 | sudo -S bash -c '{}'".format(script.replace("'", "'\\''")))
print("--- stdout ---")
print(stdout.read().decode('utf-8'))
print("--- stderr ---")
print(stderr.read().decode('utf-8'))

client.close()
