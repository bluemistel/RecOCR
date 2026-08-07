"""config.json の読み書き（旧 main.py の load_config / save_config を抽出）。"""
import json
import os

from .paths import bundle_dir, data_dir

# 書き込み先（EXE化後は EXE と同じ階層。書けなければ %LOCALAPPDATA%\RecoOCR）
CONFIG_FILE = os.path.join(data_dir(), "config.json")
# 同梱されている初期設定（書き込み先に config が無いときの元データ）
BUNDLED_CONFIG = os.path.join(bundle_dir(), "config.json")

DEFAULTS = {
    "characters": [],
    "ocr_mode": "numkey",       # デスクトップOCR完了時の挙動: clipboard | direct | numkey
    "ocr_engine": "windows",    # windows | easyocr
    "ocr_lang": "ja",
    "input_mode": "desktop",    # desktop | media
    "read_mode": "normal",      # normal | continuous（メディアモードの読み取り方式）
    "last_rect": None,          # デスクトップの前回矩形 [x, y, w, h]（グローバル座標）
    "media_region": None,       # メディア上の前回選択矩形 [x, y, w, h]（表示ウィジェット座標）
    "shortcut_key": "<ctrl>+<alt>+o",
    "preprocess": {             # OCR前処理（精度優先・速度低下）
        "enabled": False,
        "upscale": 2,
        "grayscale": True,
        "denoise": True,
        "contrast": True,
        "binarize": False,
        "invert": False,
    },
    "multi_ocr_vote": False,     # 複数条件の多数決OCR（低速・高精度）
    "remove_spaces": False,      # 認識結果の半角スペースを除去
    "correction_mode": "off",   # 日本語校正: off | suggest（候補提示）| auto（自動修正）
}


class ConfigManager:
    """設定の保持と永続化を担う薄いラッパ。"""

    def __init__(self, path: str = CONFIG_FILE):
        self.path = path
        self.data = self.load()

    def load(self) -> dict:
        data = dict(DEFAULTS)
        # 書き込み先に設定が無ければ、同梱の初期設定を読み込む
        source = self.path if os.path.exists(self.path) else BUNDLED_CONFIG
        if os.path.exists(source):
            try:
                with open(source, "r", encoding="utf-8") as f:
                    data.update(json.load(f))
            except Exception:
                pass
        return data

    def save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[config] save error: {e}")

    # 辞書風アクセス --------------------------------------------------
    def get(self, key, default=None):
        return self.data.get(key, default if default is not None else DEFAULTS.get(key))

    def set(self, key, value, *, save: bool = True) -> None:
        self.data[key] = value
        if save:
            self.save()

    @property
    def characters(self) -> list:
        return self.data.get("characters", [])
