"""CSV/TXT エクスポート（話者・台詞・プリセット・時刻の列を組み立てる）。"""
from ..models.transcript_model import TranscriptRow


def _csv_escape(value: str) -> str:
    """ダブルクォートを "" にエスケープ。"""
    return value.replace('"', '""')


def has_presets(rows: list[TranscriptRow]) -> bool:
    """1行でも「話者名,プリセット名」形式が使われているか。"""
    return any(row.preset for row in rows)


def export(rows: list[TranscriptRow], path: str, fmt: str,
           include_timestamp: bool = False,
           include_preset: bool = False) -> None:
    """rows を path へ書き出す。

    列の並びは次のとおり（[] は該当する場合のみ付く）:

        話者名, 台詞, [プリセット名], [MM:SS.mmm]

    プリセット名は、一部の合成音声ソフトが3列目を「話者に対する音声の
    プリセット」として読むため、時刻より前（3列目）に置く。
    プリセットを使っていない行は空文字にして列の位置を揃える。
    """
    with open(path, "w", encoding="utf-8", newline="") as f:
        for row in rows:
            name, preset = TranscriptRow.split_speaker(row.speaker or "")
            text = row.text or ""
            ts = TranscriptRow.format_timestamp(row.timestamp_ms)

            values = [name, text]
            if include_preset:
                values.append(preset)
            if include_timestamp:
                values.append(ts)

            if fmt == "csv":
                f.write(",".join(f'"{_csv_escape(v)}"' for v in values) + "\n")
            else:
                f.write(",".join(values) + "\n")
