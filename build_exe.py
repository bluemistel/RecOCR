"""RecoOCR を PyInstaller で EXE 化する補助スクリプト。

必ず本プロジェクトの venv の python で実行してください（重要）:

    venv\\Scripts\\python.exe -m pip install pyinstaller
    venv\\Scripts\\python.exe build_exe.py

グローバル（特に Microsoft Store 版）Python で実行すると、sys.executable が
WindowsApps のエイリアスとなり subprocess が起動できず「[Errno 2] No such file
or directory」になります。その場合は上記のように venv の python を使ってください。

生成物:
    dist/RecoOCR/RecoOCR.exe        初期設定の config.json、README.txt、LICENSE.txt を同階層に配置
    RecOCR-v<バージョン>-win64.zip  dist/RecoOCR を RecoOCR/ フォルダとして固めた配布用 zip
                                    （GitHub リリース・BOOTH 共通）
ビルド後の動作確認:  dist\\RecoOCR\\RecoOCR.exe --selftest

`--package-only` を付けると PyInstaller を実行せず、既存の dist/RecoOCR に
同梱文書を置き直して zip だけを作り直します（文書だけ直したいとき用）。
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent

# 実行時に import される主要パッケージ（欠けていると exe が動かない）
REQUIRED = ["PySide6", "pynput", "numpy", "PIL", "rapidfuzz",
            "wordfreq", "winrt", "rapidocr", "onnxruntime"]


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


def _write_default_config(path):
    """配布用に「初期設定」の config.json を生成する。

    開発環境の config.json（話者名・切り取り座標などの個人設定）は使わない。
    アプリの既定値（app.config_manager.DEFAULTS）から新規に作る。
    """
    import json
    from app.config_manager import DEFAULTS

    cfg = json.loads(json.dumps(DEFAULTS))  # ネストを含む深いコピー
    cfg["ocr_engine"] = "rapidocr"          # 同梱している既定エンジン
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=4) + "\n",
                    encoding="utf-8")


def _add_docs(dist_dir):
    """利用者向けの説明書とライセンスを EXE と同じ階層に置く。

    ダブルクリックで開けるよう、どちらも .txt で配置する。
    """
    shutil.copyfile(ROOT / "packaging" / "README.txt", dist_dir / "README.txt")
    shutil.copyfile(ROOT / "LICENSE", dist_dir / "LICENSE.txt")


def _make_zip(dist_dir):
    """dist/RecoOCR を RecoOCR/ フォルダとして zip に固める。"""
    import zipfile
    from app import __version__

    out = ROOT / f"RecOCR-v{__version__}-win64.zip"
    out.unlink(missing_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in sorted(dist_dir.rglob("*")):
            if path.is_file():
                z.write(path, Path("RecoOCR") / path.relative_to(dist_dir))
    return out


def main():
    dist_dir = ROOT / "dist" / "RecoOCR"
    if "--package-only" in sys.argv:
        if not (dist_dir / "RecoOCR.exe").exists():
            print("dist/RecoOCR/RecoOCR.exe がありません。先に通常のビルドを実行してください。")
            sys.exit(1)
        _add_docs(dist_dir)
        print(f"配布用 zip: {_make_zip(dist_dir)}")
        return

    _check_environment()

    try:
        subprocess.run(
            [sys.executable, "-m", "PyInstaller", "recoocr.spec", "--noconfirm", "--clean"],
            cwd=str(ROOT), check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"\nPyInstaller がエラー終了しました (code {e.returncode})。上のログを確認してください。")
        sys.exit(e.returncode)

    if dist_dir.exists():
        _write_default_config(dist_dir / "config.json")
        _add_docs(dist_dir)
        print(f"\n完了: {dist_dir / 'RecoOCR.exe'}")
        print("初期設定の config.json と README.txt / LICENSE.txt を EXE と同じ階層に配置しました。")
        print(f"動作確認: \"{dist_dir / 'RecoOCR.exe'}\" --selftest")
        print(f"配布用 zip: {_make_zip(dist_dir)}")


if __name__ == "__main__":
    main()
