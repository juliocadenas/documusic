import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

script = """
set -e
echo "Creando directorio y clave secreta..."
mkdir -p /etc/luks-keys
if [ ! -f /etc/luks-keys/root.key ]; then
    dd if=/dev/urandom of=/etc/luks-keys/root.key bs=1024 count=4
    chmod 0400 /etc/luks-keys/root.key
    chown root:root /etc/luks-keys/root.key

    echo "Añadiendo clave al anillo LUKS de /dev/sda3..."
    echo -n "pepe1234" > /tmp/pass
    cryptsetup luksAddKey --key-file /tmp/pass /dev/sda3 /etc/luks-keys/root.key
    rm /tmp/pass
fi

echo "Actualizando crypttab..."
sed -i 's|none luks|/etc/luks-keys/root.key luks|g' /etc/crypttab

echo "Configurando initramfs para embeber la clave..."
if ! grep -q "KEYFILE_PATTERN" /etc/cryptsetup-initramfs/conf-hook; then
    echo "KEYFILE_PATTERN=/etc/luks-keys/*.key" >> /etc/cryptsetup-initramfs/conf-hook
fi
echo "UMASK=0077" >> /etc/initramfs-tools/initramfs.conf

echo "Compilando nuevo kernel initramfs (esto tarda unos 30-60 segundos)..."
update-initramfs -u

echo "¡Completado!"
"""

stdin, stdout, stderr = client.exec_command("echo pepe1234 | sudo -S bash -c '{}'".format(script.replace("'", "'\\''")))
print("--- stdout ---")
print(stdout.read().decode('utf-8'))
print("--- stderr ---")
print(stderr.read().decode('utf-8'))

client.close()
