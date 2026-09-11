"""書き出し。

用途で形式を分けている。

- CSV / TXT : 合成音声ソフトへの取り込み用。話者名・台詞・プリセット名のみ。
              （時刻は取り込み側で意味を持たないため出力しない）
- SRT       : 字幕用。時刻が意味を持つのはこちら。
"""
from ..models.transcript_model import TranscriptRow

# SRT で終了時刻を決めるための既定値（ミリ秒）
SRT_MIN_DURATION_MS = 800      # これより短くはしない
SRT_MAX_DURATION_MS = 6000     # 次の台詞まで間が空いても、これ以上は伸ばさない
SRT_LAST_DURATION_MS = 3000    # 最後の行は次が無いのでこの長さにする
SRT_GAP_MS = 1                 # 次の字幕と重ならないようにあける間隔


def rows_with_separator(rows: list[TranscriptRow], include_preset: bool = False) -> int:
    """列の区切りと誤認されうる半角カンマを含む行数を数える。

    囲み文字を付けずに出力するため、台詞やプリセット名に半角カンマがあると
    取り込み側で列がずれる。書き出し後に注意を促すために使う。
    """
    count = 0
    for row in rows:
        _name, preset = TranscriptRow.split_speaker(row.speaker or "")
        targets = [row.text or ""]
        if include_preset:
            targets.append(preset)
        if any("," in t for t in targets):
            count += 1
    return count


def has_presets(rows: list[TranscriptRow]) -> bool:
    """1行でも「話者名,プリセット名」形式が使われているか。"""
    return any(row.preset for row in rows)


def timed_rows(rows: list[TranscriptRow]) -> list[TranscriptRow]:
    """時刻を持つ行だけを時刻順に取り出す（SRT 用）。"""
    return sorted((r for r in rows if r.timestamp_ms is not None),
                  key=lambda r: r.timestamp_ms)


def export(rows: list[TranscriptRow], path: str, fmt: str,
           include_preset: bool = False) -> None:
    """CSV / TXT を書き出す。

    列の並びは次のとおり（[] は該当する場合のみ付く）:

        話者名, 台詞, [プリセット名]

    プリセット名は、一部の合成音声ソフトが3列目を「話者に対する音声の
    プリセット」として読むため3列目に置く。
    プリセットを使っていない行は空文字にして列の位置を揃える。

    値は " で囲まない。囲むと取り込み側が引用符ごと本文として読んでしまう
    ソフトがあるため。そのぶん、台詞に半角カンマがあると列がずれるので、
    呼び出し側は rows_with_separator() で事前に確認できる。
    fmt は拡張子の区別だけで、中身は CSV / TXT とも同じ形式。
    """
    with open(path, "w", encoding="utf-8", newline="") as f:
        for row in rows:
            name, preset = TranscriptRow.split_speaker(row.speaker or "")
            values = [name, row.text or ""]
            if include_preset:
                values.append(preset)

            f.write(",".join(values) + "\n")


def format_srt_time(ms: int) -> str:
    """SRT の時刻表記 HH:MM:SS,mmm へ。"""
    ms = max(0, int(ms))
    total_seconds, millis = divmod(ms, 1000)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def export_srt(rows: list[TranscriptRow], path: str,
               include_speaker: bool = True) -> int:
    """SRT 字幕を書き出し、書き出した件数を返す。

    各行は開始時刻しか持たないため、終了時刻は次の行の開始時刻から決める。
    間が空きすぎる場合は SRT_MAX_DURATION_MS で頭打ちにし、
    最後の行は SRT_LAST_DURATION_MS の長さにする。
    時刻を持たない行（デスクトップ/画像から取り込んだ行）は対象外。
    """
    entries = timed_rows(rows)
    with open(path, "w", encoding="utf-8", newline="") as f:
        for i, row in enumerate(entries):
            start = int(row.timestamp_ms)

            if i + 1 < len(entries):
                next_start = int(entries[i + 1].timestamp_ms)
                end = min(next_start - SRT_GAP_MS, start + SRT_MAX_DURATION_MS)
            else:
                end = start + SRT_LAST_DURATION_MS
            # 同時刻や逆転があっても必ず正の長さにする
            end = max(end, start + SRT_MIN_DURATION_MS)

            name = row.speaker_name
            text = row.text or ""
            body = f"{name}：{text}" if (include_speaker and name) else text

            f.write(f"{i + 1}\n")
            f.write(f"{format_srt_time(start)} --> {format_srt_time(end)}\n")
            f.write(body + "\n\n")
    return len(entries)
