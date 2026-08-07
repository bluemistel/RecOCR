# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for RecoOCR.

既定では EasyOCR/torch は同梱しない（Windows OCR = winrt を利用、軽量）。
環境変数 RECOOCR_WITH_EASYOCR=1 のとき EasyOCR も同梱する（torch 込みで巨大）。
winrt の projected パッケージは動的 import が多いため collect_all で取り込む。
"""
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

WITH_EASYOCR = os.environ.get("RECOOCR_WITH_EASYOCR") == "1"

datas, binaries, hiddenimports = [], [], []

# winrt（PyWinRT）projected packages
for pkg in [
    "winrt",
    "winrt.windows.media.ocr",
    "winrt.windows.graphics.imaging",
    "winrt.windows.storage.streams",
    "winrt.windows.globalization",
    "winrt.windows.foundation",
    "winrt.windows.foundation.collections",
]:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# 日本語校正の依存（辞書・データファイルを含むため collect_all）
for pkg in ["sudachipy", "sudachidict_core", "wordfreq", "rapidfuzz"]:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

# アプリ内モジュール（ワーカープロセスが動的に import するため明示）
hiddenimports += collect_submodules("app")
hiddenimports += ["pynput.keyboard", "pynput.mouse"]

# 校正用データ（バイグラム言語モデル）を同梱
datas += [("app/correction/data/jp_bigram.json.gz", "app/correction/data")]

# EasyOCR を同梱する場合（RECOOCR_WITH_EASYOCR=1）
if WITH_EASYOCR:
    for pkg in ["easyocr", "torch", "torchvision", "cv2"]:
        try:
            d, b, h = collect_all(pkg)
            datas += d
            binaries += b
            hiddenimports += h
        except Exception:
            pass
    excludes = []
else:
    excludes = ["easyocr", "torch", "torchvision", "torchaudio", "cv2"]

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RecoOCR",
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="RecoOCR",
)
