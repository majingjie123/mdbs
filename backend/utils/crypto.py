import os
from cryptography.fernet import Fernet

class CryptoUtils:
    _key_file = "secret.key"
    _key = None

    @classmethod
    def _get_key_file_path(cls) -> str:
        """获取密钥文件的绝对存放路径，定位至系统 AppData 隔离区"""
        # 跨平台自动寻找 AppData/Local 目录
        if os.name == 'nt':
            app_dir = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA')
        else:
            app_dir = os.path.expanduser('~/.local/share')
            
        if not app_dir:
            return cls._key_file  # 卫语句兜底，找不到系统目录则退回到当前目录
            
        mdbs_dir = os.path.join(app_dir, "MDBS")
        try:
            os.makedirs(mdbs_dir, exist_ok=True)
            return os.path.join(mdbs_dir, cls._key_file)
        except Exception:
            return cls._key_file  # 兜底

    @classmethod
    def _get_key(cls):
        # 卫语句：已缓存直接返回
        if cls._key:
            return cls._key
            
        # 确定新物理存放路径
        new_path = cls._get_key_file_path()
        
        # 平滑向下兼容迁移：如果旧的 secret.key 存在于当前工作目录，且新路径尚无，则迁移拷贝
        if os.path.exists(cls._key_file) and not os.path.exists(new_path) and cls._key_file != new_path:
            try:
                import shutil
                shutil.copy2(cls._key_file, new_path)
            except Exception:
                pass
                
        # 加载或生成密钥
        if os.path.exists(new_path):
            with open(new_path, "rb") as f:
                cls._key = f.read()
        else:
            cls._key = Fernet.generate_key()
            with open(new_path, "wb") as f:
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
