"""設定・作業状態の保存先ディレクトリの解決。

2つの事情に対応する。

1. PyInstaller で EXE 化すると、モジュールの ``__file__`` はバンドル内部
   （onedir なら ``_internal/``）を指す。``__file__`` 基準でパスを組むと
   EXE と同じ階層に置いた ``config.json`` を読めない。
2. EXE の置き場所が書き込み不可のことがある（Program Files、読み取り専用
   メディア、Windows Defender の「フォルダーアクセスの制御」配下など）。
   その場合は %LOCALAPPDATA%\\RecoOCR へ退避しないと設定も書き起こしも失われる。

``bundle_dir()`` は同梱ファイルの場所（読み取り用）、
``data_dir()`` は実際に書き込める場所（書き込み用）を返す。
"""
import os
import sys
from functools import lru_cache

APP_NAME = "RecoOCR"


def bundle_dir() -> str:
    """同梱ファイル（初期 config.json など）が置かれている場所。"""
    if getattr(sys, "frozen", False):
        # PyInstaller 実行時: EXE と同じ階層
        return os.path.dirname(os.path.abspath(sys.executable))
    # 通常実行時: プロジェクトルート（app/ の一つ上）
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _is_writable(directory: str) -> bool:
    try:
        os.makedirs(directory, exist_ok=True)
        probe = os.path.join(directory, ".recoocr_write_test")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("")
        os.remove(probe)
        return True
    except Exception:
        return False


@lru_cache(maxsize=1)
def data_dir() -> str:
    """config.json / session.json を書き込む場所。

    既定は bundle_dir()。そこへ書けない場合は %LOCALAPPDATA%\\RecoOCR を使う。
    """
    primary = bundle_dir()
    if _is_writable(primary):
        return primary
    fallback = os.path.join(
        os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), APP_NAME)
    if _is_writable(fallback):
        print(f"[paths] '{primary}' へ書き込めないため '{fallback}' を使用します。")
        return fallback
    # どちらも不可（この場合は保存時にエラーとして扱われる）
    return primary


# 後方互換: 以前の呼び出し名
def app_dir() -> str:
    return data_dir()


def resource_path(*parts: str) -> str:
    """app/resource/ 配下の同梱リソース（アイコンなど）のパス。

    PyInstaller の datas は EXE の隣ではなく ``sys._MEIPASS``（onedir なら
    ``_internal/``）に展開されるため、bundle_dir() とは基準が異なる。
    """
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "app", "resource", *parts)
