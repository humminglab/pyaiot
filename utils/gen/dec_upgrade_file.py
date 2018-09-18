import sys
import os.path

from Crypto.Cipher import AES
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
from Crypto.Hash import SHA256
from base64 import b64decode

PRI_FILENAME = '{}/.ssh/id_rsa'.format(os.path.expanduser('~'))

if len(sys.argv) != 3:
    print("dec_upgrade_file.py in_file out_file")
    sys.exit(0)

with open(PRI_FILENAME, 'r') as f:
    rsakey = RSA.importKey(f.read())

with open(sys.argv[1], 'rb') as f:
    data = f.read()

aes_key = rsakey.decrypt(data[:256])

aes_engine = AES.new(aes_key, AES.MODE_CBC, '\x00'*16)
data = aes_engine.decrypt(data[256:])

n_pos = data.find(b'\n')
signature = b64decode(data[:n_pos])
data = data[n_pos+1:]
n_pos = data.find(b'\n')
len = int(data[:n_pos])
data = data[n_pos+1:n_pos+1+len]

verifier = PKCS1_v1_5.new(rsakey)
digest = SHA256.new()
digest.update(data)
if verifier.verify(digest, signature):
    print("The signature is authentic.")

with open(sys.argv[2], 'wb') as f:
    f.write(data)
