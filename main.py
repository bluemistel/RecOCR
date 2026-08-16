"""RecoOCR エントリポイント。

デスクトップ範囲 / 画像・動画のOCRで話者付きの台詞を書き起こすツール。

`--selftest` を付けて起動すると、GUI を出さずに OCR の自己診断を行う。
EXE 化した配布物が正しく動くかの確認や、不具合の切り分けに使う。
"""
import sys
import multiprocessing


def _selftest() -> int:
    """OCR エンジンとデータの同梱状況を確認する（GUIなし）。"""
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QImage, QPainter, QColor, QFont
    from PySide6.QtCore import Qt

    from app.paths import bundle_dir, data_dir
    from app.config_manager import ConfigManager
    from app.ocr.factory import create_engine

    app = QApplication(sys.argv)  # QImage/QFont のために必要
    ok = True

    print("=== RecoOCR self test ===")
    print(f"frozen      : {getattr(sys, 'frozen', False)}")
    print(f"bundle_dir  : {bundle_dir()}")
    print(f"data_dir    : {data_dir()}")

    cfg = ConfigManager()
    engine_name = cfg.get("ocr_engine", "rapidocr")
    lang = cfg.get("ocr_lang", "ja")
    print(f"ocr_engine  : {engine_name} / lang={lang}")

    # 日本語のテスト画像を生成
    expected = "永遠に労働を、永遠に職務を。"
    img = QImage(760, 90, QImage.Format.Format_ARGB32)
    img.fill(QColor(30, 30, 32))
    p = QPainter(img)
    p.setPen(QColor(240, 240, 240))
    f = QFont("MS Gothic")
    f.setPixelSize(34)
    p.setFont(f)
    p.drawText(img.rect(), Qt.AlignmentFlag.AlignCenter, expected)
    p.end()

    try:
        engine = create_engine(engine_name, lang)
        text = engine.recognize(img)
        print(f"OCR result  : {text}")
        if not text:
            print("NG: 文字を認識できませんでした")
            ok = False
    except Exception as e:
        print(f"NG: OCRエンジンの初期化/実行に失敗: {type(e).__name__}: {e}")
        ok = False

    # 校正（辞書＋類似字＋バイグラム文脈）の確認
    try:
        from app.correction.lm import get_lm
        from app.correction.corrector import get_corrector
        lm_ok = get_lm().ensure_loaded()
        print(f"bigram LM   : {'OK' if lm_ok else 'NG (読み込み失敗)'}")
        if not lm_ok:
            ok = False

        c = get_corrector("ja")
        c.ensure_loaded()
        print(f"分割器      : {'Sudachi' if c._tok is not None else 'SimpleTokenizer(同梱版)'}")
        src = "永速に芳働を、永満に職務を。"
        want = "永遠に労働を、永遠に職務を。"
        got = c.apply_best(src)
        print(f"校正テスト  : {src} -> {got}")
        if got != want:
            print(f"NG: 校正結果が期待と異なります（期待: {want}）")
            ok = False
        # 正しい語を壊していないか
        keep = "人口管理チームにより、追放手続きの対象となります。"
        if c.apply_best(keep) != keep:
            print(f"NG: 正しい語を誤修正しました -> {c.apply_best(keep)}")
            ok = False
    except Exception as e:
        print(f"校正        : NG {type(e).__name__}: {e}")
        ok = False

    print("=== RESULT:", "PASS" if ok else "FAIL", "===")
    return 0 if ok else 1


def main():
    # ProcessPoolExecutor + PyInstaller(onefile) 対策
    multiprocessing.freeze_support()

    if "--selftest" in sys.argv:
        sys.exit(_selftest())

    from PySide6.QtWidgets import QApplication
    from app import theme
    from app.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setStyle("Fusion")            # OS テーマに左右されず配色を統一する
    app.setPalette(theme.palette())   # チェック記号などは Fusion に描かせる
    app.setStyleSheet(theme.stylesheet())
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
