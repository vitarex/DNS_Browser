from cryptography.hazmat.primitives import serialization
import cryptography.hazmat.primitives as x
from cryptography.hazmat.backends import default_backend

rsa = x.asymmetric.rsa

a = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
    backend=default_backend()
)

print(a.private_bytes(serialization.PrivateFormat.PKCS8, serialization.Encoding.PEM, serialization.NoEncryption))
