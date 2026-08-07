"""別プロセス OCR 基盤。

- ProcessPoolExecutor でワーカープロセスを起動し、各プロセスで OCR エンジンを
  シングルトン保持する（起動時 initializer で生成）。
- ocr_job はトップレベル関数（pickle 可能）で、PNG バイト列を受け取りテキストを返す。
- OcrDispatcher(QObject) がプールを所有し、完了時に UI スレッドへ Signal で通知する。
  future.add_done_callback は別スレッドで走るため、Signal のキュー接続でマーシャルする。
"""
from concurrent.futures import ProcessPoolExecutor
import itertools

from PySide6.QtCore import QObject, Signal

# --- ワーカープロセス側 ------------------------------------------------
_ENGINE = None
_FREQ = None


def _init_worker(engine_name: str, lang: str):
    global _ENGINE
    from .factory import create_engine
    try:
        _ENGINE = create_engine(engine_name, lang)
    except Exception as e:  # 生成失敗は job 側で例外送出
        _ENGINE = e


def _freq_dict():
    global _FREQ
    if _FREQ is None:
        try:
            from wordfreq import get_frequency_dict
            _FREQ = get_frequency_dict("ja")
        except Exception:
            _FREQ = {}
    return _FREQ


def ocr_job(seq: int, png_bytes: bytes, options: dict | None = None,
            vote: bool = False) -> tuple[int, str]:
    """ワーカープロセスで実行される OCR ジョブ（前処理→OCR、必要なら多数決）。"""
    global _ENGINE
    if isinstance(_ENGINE, Exception) or _ENGINE is None:
        raise RuntimeError(f"OCRエンジン初期化に失敗: {_ENGINE}")
    from . import preprocess
    if vote:
        from . import vote as votemod
        results = []
        for opt in votemod.variants(options):
            pb = preprocess.apply(png_bytes, opt)
            results.append(_ENGINE.recognize_png_bytes(pb))
        return seq, votemod.combine(results, _freq_dict())
    png_bytes = preprocess.apply(png_bytes, options)
    return seq, _ENGINE.recognize_png_bytes(png_bytes)


# --- UI プロセス側 ----------------------------------------------------
class OcrDispatcher(QObject):
    """OCR ジョブの投入と結果通知（UI スレッドへ marshal）。"""

    result_ready = Signal(int, str)   # (seq, text)
    failed = Signal(int, str)         # (seq, error message)

    def __init__(self, engine_name: str = "windows", lang: str = "ja",
                 max_workers: int = 2, parent=None):
        super().__init__(parent)
        self.engine_name = engine_name
        self.lang = lang
        self.max_workers = max_workers
        self._seq = itertools.count(1)
        self._executor: ProcessPoolExecutor | None = None

    def _ensure_executor(self) -> ProcessPoolExecutor:
        if self._executor is None:
            self._executor = ProcessPoolExecutor(
                max_workers=self.max_workers,
                initializer=_init_worker,
                initargs=(self.engine_name, self.lang),
            )
        return self._executor

    def submit(self, png_bytes: bytes, options: dict | None = None,
               vote: bool = False) -> int:
        """OCR ジョブを投入し、識別用の seq を返す。結果は Signal で通知。

        options は前処理設定（app.ocr.preprocess.apply の引数）。
        vote=True で複数条件の多数決OCR（低速・高精度）。
        """
        seq = next(self._seq)
        executor = self._ensure_executor()
        future = executor.submit(ocr_job, seq, png_bytes, options, vote)

        def _done(fut, _seq=seq):
            try:
                _, text = fut.result()
                self.result_ready.emit(_seq, text)
            except Exception as e:
                self.failed.emit(_seq, str(e))

        future.add_done_callback(_done)
        return seq

    def restart(self, engine_name: str, lang: str) -> None:
        """エンジン/言語を変更してプールを作り直す。"""
        self.shutdown()
        self.engine_name = engine_name
        self.lang = lang

    def shutdown(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
