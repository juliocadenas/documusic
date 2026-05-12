import paramiko

HOST = "100.65.182.25"
USER = "pepe"
PASS = "pepe1234"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)

script = """
# Enable linger for pepe
loginctl enable-linger pepe

# Fix gdm3 custom.conf
cat << 'EOF' > /etc/gdm3/custom.conf
[daemon]
AutomaticLoginEnable=True
AutomaticLogin=pepe
WaylandEnable=false
EOF

# Ensure all network connections are system-wide (no permissions)
for conn in $(nmcli -t -f UUID c show); do
    nmcli connection modify "$conn" connection.permissions ""
done

# Restart gdm3 is not a good idea over SSH right now, it will kill session.
# Ensure docker is enabled
systemctl enable docker

# Check if tailscale is enabled
systemctl enable tailscaled
"""

stdin, stdout, stderr = client.exec_command("echo pepe1234 | sudo -S bash -c '{}'".format(script.replace("'", "'\\''")))
print("--- stdout ---")
print(stdout.read().decode('utf-8'))
print("--- stderr ---")
print(stderr.read().decode('utf-8'))

client.close()
