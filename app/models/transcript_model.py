"""書き起こし1行のデータモデル。"""
from dataclasses import dataclass


@dataclass
class TranscriptRow:
    """話者・台詞・（動画モードのみ）取り込み時の再生位置。"""
    speaker: str
    text: str
    timestamp_ms: int | None = None   # デスクトップ/画像モードでは None

    @staticmethod
    def format_timestamp(ms: int | None) -> str:
        """MM:SS.mmm 形式へ。None は空文字。"""
        if ms is None:
            return ""
        if ms < 0:
            ms = 0
        total_seconds, millis = divmod(int(ms), 1000)
        minutes, seconds = divmod(total_seconds, 60)
        return f"{minutes:02d}:{seconds:02d}.{millis:03d}"
