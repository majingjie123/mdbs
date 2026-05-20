import sys
import os
import logging
from pathlib import Path


def _debug_log(msg: str):
    """写入调试日志到用户目录 (打包后无控制台时的备用方案)。"""
    try:
        with open(os.path.join(os.path.expanduser('~'), 'mdbs_debug.log'), 'a', encoding='utf-8') as f:
            f.write(f"{msg}\n")
    except Exception:
        pass

# 确保 backend 包能正常导入
def _get_project_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # PyInstaller 打包后：所有文件在 _MEIPASS 目录下
        return Path(sys._MEIPASS)
    # 开发模式：脚本在 scripts/ 目录，根目录在 parent
    return Path(__file__).resolve().parent.parent

ROOT = str(_get_project_root())
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
# dependencies.py 使用 from core import ... / from models import ... 绝对导入
# 需要把 backend/ 目录也加入 sys.path
BACKEND_DIR = os.path.join(ROOT, 'backend')
if BACKEND_DIR not in sys.path and os.path.isdir(BACKEND_DIR):
    sys.path.insert(0, BACKEND_DIR)

# 直接导入 backend.main 让 PyInstaller 追踪到依赖
# 同时把 app 对象传给 uvicorn 而非用字符串导入
from backend.main import app


def _get_frontend_dist() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "frontend" / "dist"
    return Path(__file__).resolve().parent.parent / "frontend" / "dist"


def _patch_uvicorn_logging():
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(levelname)-7s %(message)s",
                "class": "logging.Formatter",
            },
            "access": {
                "format": "%(levelname)-7s %(client_addr)s - %(request_line)s %(status_code)s",
                "class": "logging.Formatter",
            },
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
            "access": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
        },
        "root": {"level": "INFO", "handlers": ["default"]},
        "loggers": {
            "uvicorn.error": {"level": "INFO", "handlers": ["default"], "propagate": False},
            "uvicorn.access": {"level": "INFO", "handlers": ["access"], "propagate": False},
        },
    }


def main():
    try:
        os.environ["MDBS_FRONTEND_DIST"] = str(_get_frontend_dist())
        host = os.environ.get("MDBS_HOST", "127.0.0.1")
        port = int(os.environ.get("MDBS_PORT", "18081"))

        # debug: write log
        _debug_log(f"Starting server at {host}:{port}")

        import threading
        import uvicorn

        def _run_server():
            try:
                uvicorn.run(app, host=host, port=port, reload=False, log_config=_patch_uvicorn_logging())
            except KeyboardInterrupt:
                pass

        # Uvicorn 在后台线程运行
        t = threading.Thread(target=_run_server, daemon=True)
        t.start()

        _debug_log("Starting pywebview...")

        # 给 uvicorn 一点启动时间
        import time
        time.sleep(1)

        # 用 pywebview 打开原生桌面窗口，内嵌前端界面
        import webview

        # 定义 JS API，暴露 save_file 给前端用于弹出原生保存文件对话框
        class Api:
            def save_file(self, filename: str, content_b64: str) -> bool:
                import webview
                result = webview.windows[0].create_file_dialog(
                    webview.SAVE_DIALOG,
                    save_filename=filename,
                )
                if result:
                    import base64
                    with open(result, 'wb') as f:
                        f.write(base64.b64decode(content_b64))
                    return True
                return False

        _debug_log("webview imported, creating window...")
        webview.create_window(
            title="MDBS",
            url=f"http://{host}:{port}/",
            width=1280,
            height=800,
            resizable=True,
            min_size=(800, 600),
            fullscreen=False,
            easy_drag=False,
            maximized=True,                   # pywebview 6.x: 窗口启动时最大化
            js_api=Api(),
        )
        _debug_log("Starting GUI loop...")
        # create_window 从主线程调用时只创建对象不显示，
        # 必须调用 start() 来启动 GUI 事件循环（阻塞直到窗口关闭）
        webview.start()
        _debug_log("Window closed, exiting")
    except Exception as e:
        import traceback
        error_msg = f"FATAL: {e}\n{''.join(traceback.format_exc())}"
        _debug_log(error_msg)
        sys.exit(1)


if __name__ == "__main__":
    # debug: write startup marker
    try:
        with open(os.path.join(os.path.expanduser('~'), 'mdbs_debug.log'), 'w') as f:
            f.write("start\n")
    except Exception:
        pass
    main()