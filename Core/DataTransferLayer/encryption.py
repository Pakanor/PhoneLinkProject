import os
import base64
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class DecryptionError(Exception):
    pass


class Encryption:

    CIPHER_SUITE = "AES-256-GCM"
    KEY_SIZE = 32
    NONCE_SIZE = 12
    TAG_SIZE = 16
    CURVE = ec.SECP256R1
    HKDF_INFO = b"phonelink-ecdhe-aes256gcm"

    def __init__(self, shared_key: bytes = None):
        if shared_key is None:
            self.shared_key = os.urandom(self.KEY_SIZE)
        else:
            assert len(shared_key) == self.KEY_SIZE, f"Klucz musi mieć {self.KEY_SIZE} bajtów"
            self.shared_key = shared_key

    @staticmethod
    def generate_key() -> bytes:
        return os.urandom(Encryption.KEY_SIZE)

    @staticmethod
    def derive_key(password: str, salt: bytes = None) -> tuple:
        try:
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2

            if salt is None:
                salt = os.urandom(16)

            kdf = PBKDF2(
                algorithm=hashes.SHA256(),
                length=Encryption.KEY_SIZE,
                salt=salt,
                iterations=100000,
            )
            key = kdf.derive(password.encode())
            return key, salt
        except ImportError:
            print("[Warning] PBKDF2 niedostępny, używam fallback (OS urandom)")
            if salt is None:
                salt = os.urandom(16)
            return os.urandom(Encryption.KEY_SIZE), salt

    @staticmethod
    def generate_key_pair() -> ec.EllipticCurvePrivateKey:
        return ec.generate_private_key(Encryption.CURVE())

    @staticmethod
    def public_key_b64(private_key: ec.EllipticCurvePrivateKey) -> str:
        public_bytes = private_key.public_key().public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint,
        )
        return base64.b64encode(public_bytes).decode()

    @staticmethod
    def derive_key_from_secret(shared_secret: bytes) -> bytes:
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=Encryption.KEY_SIZE,
            salt=None,
            info=Encryption.HKDF_INFO,
        )
        return hkdf.derive(shared_secret)

    @staticmethod
    def derive_shared_key(
        private_key: ec.EllipticCurvePrivateKey, peer_public_key_b64: str
    ) -> bytes:
        peer_public_bytes = base64.b64decode(peer_public_key_b64)
        peer_public_key = ec.EllipticCurvePublicKey.from_encoded_point(
            Encryption.CURVE(), peer_public_bytes
        )
        shared_secret = private_key.exchange(ec.ECDH(), peer_public_key)
        return Encryption.derive_key_from_secret(shared_secret)

    def encrypt(self, plaintext: bytes) -> bytes:
        nonce = os.urandom(self.NONCE_SIZE)
        cipher = AESGCM(self.shared_key)
        ciphertext = cipher.encrypt(nonce, plaintext, None)

        return nonce + ciphertext

    def decrypt(self, encrypted_data: bytes) -> bytes:
        nonce = encrypted_data[:self.NONCE_SIZE]
        ciphertext_with_tag = encrypted_data[self.NONCE_SIZE:]

        cipher = AESGCM(self.shared_key)
        try:
            plaintext = cipher.decrypt(nonce, ciphertext_with_tag, None)
        except InvalidTag as e:
            raise DecryptionError("Błąd autentykacji AES-GCM (uszkodzone/zmodyfikowane dane)") from e
        return plaintext
