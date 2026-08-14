"""文件存储包

从 file_watcher.py 整合而来。
"""
from infra.storage.file_watcher import start_file_watcher, stop_file_watcher

__all__ = [
    "start_file_watcher", "stop_file_watcher",
]
