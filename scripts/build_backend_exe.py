import PyInstaller.__main__

name = "mdbs-server"

params = [
    "scripts/run_backend.py",
    "--name=" + name,
    "--noconsole",
    "--onedir",
    "--clean",
    "--noconfirm",
    "--icon=icon.ico",
    "--paths=.",
    "--paths=backend",
    "--add-data",
    "frontend/dist;frontend/dist",
    "--hidden-import", "uvicorn.protocols.http.auto",
    "--hidden-import", "uvicorn.protocols.websockets.auto",
    "--hidden-import", "uvicorn.loops.auto",
    "--hidden-import", "uvicorn.logging",
    "--hidden-import", "uvicorn.middleware.proxy_headers",
    "--hidden-import", "httptools",
    "--hidden-import", "websockets",
    "--hidden-import", "watchfiles",
    "--hidden-import", "pg8000.native",
    "--hidden-import", "sqlparse",
    "--hidden-import", "openpyxl",
    "--hidden-import", "fpdf",
    "--hidden-import", "pymysql",
    "--hidden-import", "webview",
    "--collect-all", "cryptography",
    "--collect-all", "paramiko",
    "--collect-all", "openpyxl",
    "--exclude-module", "PyQt6",
    "--exclude-module", "tkinter",
    "--exclude-module", "pystray",
    "--exclude-module", "PIL",
]

PyInstaller.__main__.run(params)