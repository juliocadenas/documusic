import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

script = """
CONF_FILE="/etc/gdm3/custom.conf"

# Asegurar que el archivo existe (a veces en Pop OS es daemon.conf)
if [ ! -f "$CONF_FILE" ]; then
    CONF_FILE="/etc/gdm3/daemon.conf"
fi

if grep -q "AutomaticLoginEnable" "$CONF_FILE"; then
    sed -i 's/^#.*AutomaticLoginEnable.*/AutomaticLoginEnable = true/' "$CONF_FILE"
    sed -i 's/^.*AutomaticLoginEnable.*/AutomaticLoginEnable = true/' "$CONF_FILE"
else
    sed -i '/\\[daemon\\]/a AutomaticLoginEnable = true' "$CONF_FILE"
fi

if grep -q "AutomaticLogin" "$CONF_FILE" | grep -v "AutomaticLoginEnable"; then
    sed -i 's/^#.*AutomaticLogin =.*/AutomaticLogin = pepe/' "$CONF_FILE"
    sed -i 's/^.*AutomaticLogin =.*/AutomaticLogin = pepe/' "$CONF_FILE"
else
    sed -i '/\\[daemon\\]/a AutomaticLogin = pepe' "$CONF_FILE"
fi

# Hacer que networkmanager conecte sin login
nmcli connection modify "$(nmcli -t -f NAME c show --active | head -n 1)" connection.permissions ""

echo "Auto-Login y Red Global configurados."
"""

stdin, stdout, stderr = client.exec_command("echo pepe1234 | sudo -S bash -c '{}'".format(script.replace("'", "'\\''")))
print(stdout.read().decode('utf-8'))
print(stderr.read().decode('utf-8'))

client.close()
