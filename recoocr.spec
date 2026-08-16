# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for RecoOCR.

同梱するOCRは RapidOCR（PP-OCR / ONNX Runtime）と Windows OCR（winrt）の2種。
torch 系・EasyOCR は同梱しない。
Sudachi 辞書（200MB超）も同梱せず、校正は語彙ベースの軽量分割にフォールバックする
（実測で Sudachi 使用時と同一の校正結果が得られている）。
PP-OCR の medium モデル（134MB）も同梱しない（small の方が高精度だったため）。
"""
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas, binaries, hiddenimports = [], [], []

# winrt（PyWinRT）projected packages … Windows OCR 用
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

# OCR / 校正の依存（モデル・データファイルを含むため collect_all）
for pkg in ["rapidocr", "onnxruntime", "wordfreq", "rapidfuzz"]:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

# PP-OCR の medium モデルは同梱しない（small のみでサイズを抑える）
datas = [x for x in datas if "medium" not in os.path.basename(x[0]).lower()]

# アプリ内モジュール（ワーカープロセスが動的に import するため明示）
hiddenimports += collect_submodules("app")
hiddenimports += ["pynput.keyboard", "pynput.mouse"]

# 校正用データ（バイグラム言語モデル）を同梱
datas += [("app/correction/data/jp_bigram.json.gz", "app/correction/data")]

# 同梱しないもの（サイズ削減）
excludes = [
    "easyocr", "torch", "torchvision", "torchaudio",     # EasyOCR 系
    "sudachipy", "sudachidict_core",                     # 校正は軽量分割にフォールバック
    "scipy", "skimage", "matplotlib", "sklearn", "pandas",
]

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
