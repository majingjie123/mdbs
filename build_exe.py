import os
import sys
import PyInstaller.__main__

def build():
    # 基础配置
    name = "database"
    entry_point = "app.py"
    
    # 打包参数
    params = [
        entry_point,
        f'--name={name}',
        '--noconsole',          # 不显示控制台窗口
        '--onefile',            # 打包为单文件
        '--clean',              # 清理缓存
        '--icon=icon.ico',
    ]
    
    # 额外的数据文件 (如果有)
    # params.extend(['--add-data', 'README.md;.'])
    
    # 确保依赖库被正确包含
    # 某些库如 pg8000 可能需要显式包含
    # params.extend(['--hidden-import', 'pg8000.native'])

    print(f"开始打包 {name}...")
    PyInstaller.__main__.run(params)
    print("打包完成，请在 dist 目录下查看生成的 EXE。")

if __name__ == "__main__":
    build()
