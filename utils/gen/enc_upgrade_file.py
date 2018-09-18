import sys
import os.path

from Crypto.Cipher import AES
from Crypto import Random
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
from Crypto.Hash import SHA256
from base64 import b64encode

PUB_FILENAME = '{}/.ssh/id_rsa.pub'.format(os.path.expanduser('~'))
PRI_FILENAME = '{}/.ssh/id_rsa'.format(os.path.expanduser('~'))

if len(sys.argv) != 3:
    print("enc_upgrade_file.py in_file out_file")
    sys.exit(0)

with open(PRI_FILENAME, 'r') as f:
    rsakey = RSA.importKey(f.read())

with open(sys.argv[1], 'rb') as f:
    data = f.read()

signer = PKCS1_v1_5.new(rsakey)
digest = SHA256.new()
digest.update(data)
sign = signer.sign(digest)
b64_sign = b64encode(sign)

with open(PUB_FILENAME, 'r') as f:
    rsakey = RSA.importKey(f.read())

rngfile = Random.new()
aes_key = rngfile.read(16)

hd = rsakey.encrypt(aes_key, 28)

data_src = b64_sign + b'\n%d\n' % len(data) + data
added = 16 - (len(data_src) % 16)
if added != 16:
    data_src +=  b'\x00' * added

aes_engine = AES.new(aes_key, AES.MODE_CBC, '\x00'*16)
enc_data = aes_engine.encrypt(data_src)

with open(sys.argv[2], 'wb') as f:
    f.write(hd[0])
    f.write(enc_data)
