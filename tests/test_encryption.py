import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Core.DataTransferLayer.encryption import Encryption

def test_encrypt_decrypt():
    enc = Encryption()
    plaintext = "Testowa wiadomość".encode("utf-8")
    
    encrypted = enc.encrypt(plaintext)
    assert encrypted != plaintext, "Zaszyfrowany tekst nie może być równy plaintext"

    decrypted = enc.decrypt(encrypted)
    assert decrypted == plaintext, "Odszyfrowany tekst musi być równy oryginalnemu"

def test_key_length():
    key = Encryption.generate_key()
    assert len(key) == Encryption.KEY_SIZE

def test_b64_encoding():
    enc = Encryption()
    key_b64 = enc.get_key_b64()
    
    assert isinstance(key_b64, str)
    
    enc2 = Encryption.from_b64(key_b64)
    assert enc2.shared_key == enc.shared_key, "Odtworzony klucz musi być taki sam"

def test_custom_key():
    key = Encryption.generate_key()
    enc = Encryption(key)
    assert enc.shared_key == key

def test_encrypt_decrypt_multiple():
    enc = Encryption()
    messages = [b"Hello", b"123456", b"!@#$%^&*()"]
    
    for msg in messages:
        encrypted = enc.encrypt(msg)
        decrypted = enc.decrypt(encrypted)
        assert decrypted == msg

def test_wrong_key_fails():
    enc1 = Encryption()
    enc2 = Encryption()
    
    plaintext = b"Sekret"
    encrypted = enc1.encrypt(plaintext)
    
    with pytest.raises(Exception):
        enc2.decrypt(encrypted)

def test_derive_key_returns_correct_length():
    key, salt = Encryption.derive_key("haslo123")
    assert len(key) == Encryption.KEY_SIZE
    assert len(salt) == 16
