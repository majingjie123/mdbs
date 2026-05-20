"""MDBS 打包入口

供 PyInstaller 打包使用。将 project root 和 backend/ 加入 sys.path，
然后启动 uvicorn + pywebview 桌面窗口。

由 mdbs-server.spec 构建，spec 已配置 pathex 以确保 PyInstaller
分析阶段能找到所有 backend 内部模块。
"""
import sys
import os
import logging
from pathlib import Path


def _debug_log(msg: str):
    try:
        with open(os.path.join(os.path.expanduser('~'), 'mdbs_debug.log'), 'a', encoding='utf-8') as f:
            f.write(f"{msg}\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# sys.path 设置（打包后 _MEIPASS / 开发模式）
# ---------------------------------------------------------------------------
def _get_project_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


ROOT = str(_get_project_root())
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
BACKEND_DIR = os.path.join(ROOT, 'backend')
if BACKEND_DIR not in sys.path and os.path.isdir(BACKEND_DIR):
    sys.path.insert(0, BACKEND_DIR)

from backend.main import app


def _get_frontend_dist() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "frontend" / "dist"
    return Path(__file__).resolve().parent / "frontend" / "dist"


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

        _debug_log(f"Starting server at {host}:{port}")

        import threading
        import uvicorn

        def _run_server():
            try:
                uvicorn.run(app, host=host, port=port, reload=False, log_config=_patch_uvicorn_logging())
            except KeyboardInterrupt:
                pass

        t = threading.Thread(target=_run_server, daemon=True)
        t.start()

        _debug_log("Starting pywebview...")
        import time
        time.sleep(1)

        import webview

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
            maximized=True,
            js_api=Api(),
        )
        _debug_log("Starting GUI loop...")
        webview.start()
        _debug_log("Window closed, exiting")
    except Exception as e:
        import traceback
        error_msg = f"FATAL: {e}\n{''.join(traceback.format_exc())}"
        _debug_log(error_msg)
        sys.exit(1)


if __name__ == "__main__":
    try:
        with open(os.path.join(os.path.expanduser('~'), 'mdbs_debug.log'), 'w') as f:
            f.write("start\n")
    except Exception:
        pass
    main()
