import os
import json
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import base64

class Encryption:
    
    CIPHER_SUITE = "AES-256-GCM"
    KEY_SIZE = 32  
    NONCE_SIZE = 12  
    TAG_SIZE = 16  
    
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
            from cryptography.hazmat.primitives import hashes
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
    
    def encrypt(self, plaintext: bytes) -> bytes:
        nonce = os.urandom(self.NONCE_SIZE)
        cipher = AESGCM(self.shared_key)
        ciphertext = cipher.encrypt(nonce, plaintext, None)  
        
        return nonce + ciphertext
    
    def decrypt(self, encrypted_data: bytes) -> bytes:
        nonce = encrypted_data[:self.NONCE_SIZE]
        ciphertext_with_tag = encrypted_data[self.NONCE_SIZE:]
        
        cipher = AESGCM(self.shared_key)
        plaintext = cipher.decrypt(nonce, ciphertext_with_tag, None)
        return plaintext
    
    def get_key_b64(self) -> str:
        return base64.b64encode(self.shared_key).decode()
    
    @staticmethod
    def from_b64(key_b64: str) -> "Encryption":
        key = base64.b64decode(key_b64)
        return Encryption(key)
