import sys
import os
import logging
from pathlib import Path

# 确保项目根目录在 sys.path 中，backend 包才能被 uvicorn 正常导入
ROOT = str(Path(__file__).resolve().parent.parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


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
    os.environ["MDBS_FRONTEND_DIST"] = str(_get_frontend_dist())
    host = os.environ.get("MDBS_HOST", "127.0.0.1")
    port = int(os.environ.get("MDBS_PORT", "18080"))
    print(f"  MDBS backend: http://{host}:{port}/")
    import uvicorn
    uvicorn.run("backend.main:app", host=host, port=port, reload=False, log_config=_patch_uvicorn_logging())


if __name__ == "__main__":
    main()