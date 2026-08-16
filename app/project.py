"""プロジェクト（作業状態）の管理。

書き起こしは以下の2つの状態のどちらかで保持される。

- 未保存: 名前を付けていない状態。`session.json`（自動保存）に書かれ、
  UI 上は「新しいプロジェクト」として扱う。
- 保存済み: ユーザーが名前を付けたファイル（*.recoocr.json）。
  以降の自動保存はそのファイルに対して行われる。

プロジェクトを閉じると未保存状態へ戻り、書き起こしは空になる。
"""
import json
import os

from .paths import data_dir

EXT = ".recoocr.json"
UNTITLED = "新しいプロジェクト"
FORMAT_VERSION = 1


class Project:
    """現在開いているプロジェクトの状態。"""

    def __init__(self):
        self.path: str | None = None      # None = 未保存（session.json 運用）

    # --- 状態 -------------------------------------------------------
    @property
    def is_saved(self) -> bool:
        return self.path is not None

    @property
    def name(self) -> str:
        if not self.path:
            return UNTITLED
        base = os.path.basename(self.path)
        return base[:-len(EXT)] if base.endswith(EXT) else os.path.splitext(base)[0]

    def storage_path(self) -> str:
        """実際に書き込む先（未保存なら session.json）。"""
        return self.path or os.path.join(data_dir(), "session.json")

    # --- 操作 -------------------------------------------------------
    def open(self, path: str):
        self.path = path

    def close(self):
        self.path = None

    def save_as(self, path: str):
        if not path.endswith(EXT):
            path += EXT
        self.path = path
        return path


# --- 入出力 ----------------------------------------------------------
def write(path: str, rows: list, extra: dict | None = None) -> None:
    """プロジェクト/セッションを書き出す（直前の内容は .bak に退避）。"""
    data = {"version": FORMAT_VERSION, "rows": rows}
    if extra:
        data.update(extra)
    if os.path.exists(path):
        try:
            import shutil
            shutil.copyfile(path, path + ".bak")
        except Exception:
            pass
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def default_dir() -> str:
    """プロジェクトの既定の保存先（<データ領域>/projects）。"""
    d = os.path.join(data_dir(), "projects")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        return data_dir()
    return d
