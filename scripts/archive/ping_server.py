import paramiko
import sys
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    c.connect('100.65.182.25', username='pepe', password='pepe1234', timeout=10)
    print('SUCCESS')
except Exception as e:
    print('FAILED:', e)
    sys.exit(1)
