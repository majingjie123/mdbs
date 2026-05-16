import os
from cryptography.fernet import Fernet

class CryptoUtils:
    _key_file = "secret.key"
    _key = None

    @classmethod
    def _get_key(cls):
        if cls._key:
            return cls._key
        
        if os.path.exists(cls._key_file):
            with open(cls._key_file, "rb") as f:
                cls._key = f.read()
        else:
            cls._key = Fernet.generate_key()
            with open(cls._key_file, "wb") as f:
                f.write(cls._key)
        return cls._key

    @classmethod
    def encrypt(cls, text: str) -> str:
        """加密文本，返回字符串"""
        if not text:
            return ""
        f = Fernet(cls._get_key())
        return f.encrypt(text.encode()).decode()

    @classmethod
    def decrypt(cls, encrypted_text: str) -> str:
        """解密文本，返回原字符串"""
        if not encrypted_text:
            return ""
        try:
            f = Fernet(cls._get_key())
            return f.decrypt(encrypted_text.encode()).decode()
        except Exception:
            return "解密失败"
