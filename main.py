"""RecoOCR エントリポイント。

デスクトップ範囲 / 画像・動画のOCRで話者付き台詞を書き起こすツール。
"""
import sys
import multiprocessing

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow


def main():
    # ProcessPoolExecutor + PyInstaller(onefile) 対策
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
