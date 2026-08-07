"""RecoOCR を PyInstaller で EXE 化する補助スクリプト。

必ず本プロジェクトの venv の python で実行してください（重要）:

    venv\\Scripts\\python.exe -m pip install pyinstaller
    venv\\Scripts\\python.exe build_exe.py

グローバル（特に Microsoft Store 版）Python で実行すると、sys.executable が
WindowsApps のエイリアスとなり subprocess が起動できず「[Errno 2] No such file
or directory」になります。その場合は上記のように venv の python を使ってください。

生成物: dist/RecoOCR/RecoOCR.exe（config.json は同階層にコピーされます）。

既定は Windows OCR 版（軽量）。EasyOCR も同梱したい場合:
    venv\\Scripts\\python.exe build_exe.py --with-easyocr
    （torch を含むため非常に大きく・ビルドに時間がかかります）
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent

# 実行時に import される主要パッケージ（欠けていると exe が動かない）
REQUIRED = ["PySide6", "pynput", "numpy", "PIL", "rapidfuzz", "sudachipy",
            "sudachidict_core", "wordfreq", "winrt"]


def _check_environment():
    exe = Path(sys.executable)
    print(f"使用 Python: {exe}")
    if "WindowsApps" in str(exe):
        print("警告: Microsoft Store 版 Python の可能性があります。"
              "ビルドに失敗する場合は venv の python を使ってください:\n"
              "    venv\\Scripts\\python.exe build_exe.py")
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller が未インストールです:\n"
              f"    \"{exe}\" -m pip install pyinstaller")
        sys.exit(1)
    missing = []
    for mod in REQUIRED:
        try:
            __import__(mod)
        except Exception:
            missing.append(mod)
    if missing:
        print("次の依存が現在の Python に見つかりません: " + ", ".join(missing))
        print("この python は venv のものですか? 依存をインストールしてください:\n"
              f"    \"{exe}\" -m pip install -r requirements.txt")
        sys.exit(1)


def main():
    with_easyocr = "--with-easyocr" in sys.argv
    _check_environment()

    env = dict(os.environ)
    if with_easyocr:
        env["RECOOCR_WITH_EASYOCR"] = "1"
        print("EasyOCR を同梱します（torch 込みで巨大・時間がかかります）。")

    try:
        subprocess.run(
            [sys.executable, "-m", "PyInstaller", "recoocr.spec", "--noconfirm", "--clean"],
            cwd=str(ROOT), check=True, env=env,
        )
    except subprocess.CalledProcessError as e:
        print(f"\nPyInstaller がエラー終了しました (code {e.returncode})。上のログを確認してください。")
        sys.exit(e.returncode)

    dist_dir = ROOT / "dist" / "RecoOCR"
    if dist_dir.exists():
        import json
        cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        if not with_easyocr and cfg.get("ocr_engine") == "easyocr":
            # EasyOCR 非同梱ビルドでは exe 単体で動くよう Windows OCR に切替
            cfg["ocr_engine"] = "windows"
            print("注意: EasyOCR 非同梱のため、同梱 config は Windows OCR に設定しました。")
        (dist_dir / "config.json").write_text(
            json.dumps(cfg, ensure_ascii=False, indent=4), encoding="utf-8")
        print(f"\n完了: {dist_dir / 'RecoOCR.exe'}")
        print("config.json を EXE と同じ階層に配置しました（実行時に読み書きします）。")


if __name__ == "__main__":
    main()
