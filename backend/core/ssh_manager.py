import socket
import logging
import paramiko

# 兼容性修复: paramiko 3.x/4.x 移除了 DSSKey，但 sshtunnel 可能仍会引用它
if not hasattr(paramiko, 'DSSKey'):
    paramiko.DSSKey = None

from sshtunnel import SSHTunnelForwarder

# 禁用 sshtunnel 的详细日志，除非需要调试
logging.getLogger('sshtunnel').setLevel(logging.ERROR)

class SSHTunnelManager:
    _instance = None
    _active_tunnels = {} # {cache_key: (tunnel_object, fingerprint)}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SSHTunnelManager, cls).__new__(cls)
        return cls._instance

    def start_tunnel(self, conn_data):
        """
        根据连接配置启动 SSH 隧道
        返回 (local_host, local_port)
        """
        # 1. 生成极度详尽的配置指纹
        ssh_config_str = (
            f"host:{conn_data.get('ssh_host')}:{conn_data.get('ssh_port', 22)}|"
            f"user:{conn_data.get('ssh_user')}:{conn_data.get('ssh_auth_type')}|"
            f"pw:{conn_data.get('ssh_password')}|"
            f"key:{conn_data.get('ssh_key_path')}|"
            f"phrase:{conn_data.get('ssh_key_phrase')}|"
            f"target:{conn_data.get('ssh_remote_host') or conn_data.get('host')}:"
            f"{conn_data.get('ssh_remote_port') or conn_data.get('port')}"
        )
        
        # 2. 确定缓存使用的 Key
        conn_id = conn_data.get('id')
        cache_key = f"id_{conn_id}" if conn_id else "temp_new_conn"

        if cache_key in self._active_tunnels:
            tunnel, old_fingerprint = self._active_tunnels[cache_key]
            # 只有指纹完全一致且隧道活跃，才复用
            if old_fingerprint == ssh_config_str and tunnel.is_active:
                return '127.0.0.1', tunnel.local_bind_port
            else:
                self.stop_tunnel(cache_key)

        # 3. 校验并建立新隧道
        ssh_host = conn_data.get('ssh_host')
        if not ssh_host:
            raise Exception("未填写 SSH 主机地址")
            
        local_port = conn_data.get('ssh_local_port')
        if local_port:
            local_port = int(local_port)
        else:
            local_port = self._find_free_port()

        ssh_config = {
            'ssh_address_or_host': (ssh_host, int(conn_data.get('ssh_port', 22))),
            'ssh_username': conn_data.get('ssh_user'),
            'remote_bind_address': (conn_data.get('ssh_remote_host') or conn_data.get('host'), 
                                    int(conn_data.get('ssh_remote_port') or conn_data.get('port'))),
            'local_bind_address': ('127.0.0.1', local_port),
            'set_keepalive': 30
        }

        if conn_data.get('ssh_auth_type') == 'password':
            ssh_config['ssh_password'] = conn_data.get('ssh_password')
        else:
            ssh_config['ssh_pkey'] = conn_data.get('ssh_key_path')
            if conn_data.get('ssh_key_phrase'):
                ssh_config['ssh_private_key_password'] = conn_data.get('ssh_key_phrase')

        try:
            import time
            tunnel = SSHTunnelForwarder(**ssh_config)
            tunnel.start()
            # 增加极短的延迟，确保隧道完全打通
            time.sleep(0.2)
            self._active_tunnels[cache_key] = (tunnel, ssh_config_str)
            return '127.0.0.1', tunnel.local_bind_port
        except Exception as e:
            if cache_key in self._active_tunnels: del self._active_tunnels[cache_key]
            raise Exception(f"SSH 隧道建立失败: {str(e)}")

    def stop_tunnel(self, key):
        """停止隧道，支持传入 ID (int) 或 cache_key (str)"""
        cache_key = key if isinstance(key, str) and (key.startswith('id_') or key == 'temp_new_conn') else f"id_{key}"
        if cache_key in self._active_tunnels:
            try:
                tunnel_info = self._active_tunnels.pop(cache_key)
                tunnel = tunnel_info[0] if isinstance(tunnel_info, tuple) else tunnel_info
                if tunnel.is_active:
                    tunnel.stop()
            except:
                pass

    def stop_all_tunnels(self):
        """停止所有活跃隧道"""
        for key in list(self._active_tunnels.keys()):
            self.stop_tunnel(key)

    def _find_free_port(self):
        """寻找一个可用的本地端口"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            return s.getsockname()[1]

    def test_ssh_connection(self, conn_data):
        """仅测试 SSH 连接是否通畅"""
        import paramiko
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        ssh_host = conn_data['ssh_host']
        ssh_port = int(conn_data.get('ssh_port', 22))
        ssh_user = conn_data['ssh_user']
        auth_type = conn_data['ssh_auth_type']
        
        try:
            if auth_type == 'password':
                ssh.connect(ssh_host, port=ssh_port, username=ssh_user, 
                            password=conn_data.get('ssh_password'), timeout=10)
            else:
                ssh.connect(ssh_host, port=ssh_port, username=ssh_user, 
                            key_filename=conn_data.get('ssh_key_path'),
                            passphrase=conn_data.get('ssh_key_phrase'), timeout=10)
            ssh.close()
            return True, "SSH 连接成功"
        except Exception as e:
            return False, f"SSH 连接失败: {str(e)}"
