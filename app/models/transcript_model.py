"""書き起こし1行のデータモデル。"""
from dataclasses import dataclass

# 話者名とプリセット名の区切り文字。
# 一部の合成音声ソフトは CSV/TXT の3列目を「話者に対する音声プリセット」として
# 読むため、話者名を「話者名,プリセット名」と書けるようにしている。
PRESET_SEP = ","


@dataclass
class TranscriptRow:
    """話者・台詞・（動画モードのみ）取り込み時の再生位置。

    speaker には「話者名,プリセット名」の形式を入れられる。
    アプリ内では分割せずそのまま保持し、書き出し時にだけ列を分ける
    （同じ話者かどうかの判定は行わない）。
    """
    speaker: str
    text: str
    timestamp_ms: int | None = None   # デスクトップ/画像モードでは None

    @staticmethod
    def split_speaker(speaker: str) -> tuple[str, str]:
        """「話者名,プリセット名」を (話者名, プリセット名) に分ける。

        区切り文字が無ければプリセット名は空文字。
        2つ目以降の区切り文字はプリセット名の一部として扱う。
        """
        if not speaker:
            return "", ""
        if PRESET_SEP in speaker:
            name, preset = speaker.split(PRESET_SEP, 1)
            return name.strip(), preset.strip()
        return speaker.strip(), ""

    @property
    def speaker_name(self) -> str:
        return self.split_speaker(self.speaker)[0]

    @property
    def preset(self) -> str:
        return self.split_speaker(self.speaker)[1]

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
