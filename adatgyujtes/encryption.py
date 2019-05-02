# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
import uuid
from os import urandom

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric.padding import (
    OAEP,
    MGF1,
)
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.hashes import SHA1
from cryptography.hazmat.primitives import serialization

ADATGYUJTES_TEST_PUBLIC_KEY = b'-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0X0zr9Gkh1JKHTVCfxVS\n4Kn+828BJmHZb6zftGzfNZA1xCB6kVfskliWfQa+VwxYqPrqRzWQV8JhE0Gw23wL\n/+i1YcJDNQOZ+pjd+ALdU6K6xrZqwW2pDHbwO5ZhtbfQuPxQPFyGl1zG1MOqEY9o\nvmg2qcCEdI4TvVjEaPCc9YX4XXxq+Dwv6hxarh6lfkozJcwPhPvNrOMdlLRrJg4T\n/SnKfJWLE2E/4g412m6sVO/S6nJXAJmTk9clNq8qP3peFNSoFPJQ84jh93bPmHmy\n+8O7OK8bFd60RT+joCTL+1hcorFMyTiCv3BgYKkrsKQIO7ZMuUGj2nzITuX8gQDQ\nDQIDAQAB\n-----END PUBLIC KEY-----\n'

class KeyResolver:
    def __init__(self):
        self.keys = {}

    def put_key(self, key):
        self.keys[key.get_kid()] = key

    def resolve_key(self, kid):
        return self.keys[kid]

serialization.NoEncryption

class PublicRSAKeyWrapper:
    def __init__(self, public_key):
        self.public_key = serialization.load_pem_public_key(public_key, default_backend())
        self.kid = 'local:AdatgyujtesPublicKey' 

    def wrap_key(self, key, algorithm='RSA'):
        if algorithm == 'RSA':
            return self.public_key.encrypt(key,
                                           OAEP(
                                               mgf=MGF1(algorithm=SHA1()),
                                               algorithm=SHA1(),
                                               label=None)
                                           )

        raise ValueError(_ERROR_UNKNOWN_KEY_WRAP_ALGORITHM)

    def unwrap_key(self, key, algorithm):
        raise NotImplementedError

    def get_key_wrap_algorithm(self):
        return 'RSA'

    def get_kid(self):
        return self.kid
