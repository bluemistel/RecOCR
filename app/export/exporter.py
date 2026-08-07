"""CSV/TXT エクスポート（旧 export_list を拡張、timestamp 列対応）。"""
from ..models.transcript_model import TranscriptRow


def _csv_escape(value: str) -> str:
    """ダブルクォートを "" にエスケープ。"""
    return value.replace('"', '""')


def export(rows: list[TranscriptRow], path: str, fmt: str,
           include_timestamp: bool = False) -> None:
    """rows を path へ書き出す。

    fmt="csv": "話者","台詞"[,"MM:SS.mmm"]
    fmt="txt": 話者,台詞[,MM:SS.mmm]
    include_timestamp=True のときのみ時刻列を付ける（動画モード）。
    """
    with open(path, "w", encoding="utf-8", newline="") as f:
        for row in rows:
            speaker = row.speaker or ""
            text = row.text or ""
            ts = TranscriptRow.format_timestamp(row.timestamp_ms)
            if fmt == "csv":
                cols = [f'"{_csv_escape(speaker)}"', f'"{_csv_escape(text)}"']
                if include_timestamp:
                    cols.append(f'"{_csv_escape(ts)}"')
                f.write(",".join(cols) + "\n")
            else:
                cols = [speaker, text]
                if include_timestamp:
                    cols.append(ts)
                f.write(",".join(cols) + "\n")
