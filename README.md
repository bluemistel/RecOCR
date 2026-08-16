# RecoOCR

デスクトップ画面、または画像・動画から指定範囲を日本語OCRで連続的に読み取り、
話者（1〜9キーで選択）付きの台詞として CSV / TXT に書き起こすツール。

## 特長

- **2つの入力ソース（切替可能）**
  - **デスクトップOCR**: ホットキー（既定 `Ctrl+Alt+O`）で画面を矩形選択して読み取り。
  - **メディア**: 画像（jpg/png/bmp/webp 等）・動画（mp4/mkv/avi 等）をドラッグ&ドロップで読み込み、再生しながら領域を指定して読み取り。
- **2つの読み取りモード（メディア）**
  - **通常モード**: 一時停止 → 1〜9キー → そのフレームをOCR → 1行追加（都度確認・編集）。
  - **連続モード**: 再生を止めず 1〜9キー押下ごとに「…認識中」行を即挿入し、別プロセスOCRの結果を順次差し替え。
- **ブックマーク（動画）**: 取り込み時の再生位置を各行に記録。時刻セルをクリックでその位置へシーク。
- **作業状態の自動保存**: 追加・編集・削除のたびに `session.json` へ自動保存し、次回起動時に復元（クラッシュしても書き起こしは失われません）。「リストクリア」で消去できます。
- **OCRエンジン（3種切替）**:
  - **RapidOCR / PP-OCR**（推奨）— PaddleOCR の PP-OCR モデルを ONNX Runtime で実行。torch 不要で軽量。**ディザ・低解像度のゲーム字幕に強い**。
  - **Windows OCR** — OS 標準。最軽量で、鮮明な画像では最高精度。
  - **EasyOCR** — 任意（別途 `pip install easyocr`、torch 同梱で重い）。

  簡易ベンチマーク（合成した日本語字幕・文字誤り率 CER、低いほど良い）:

  | 画像の状態 | Windows OCR | RapidOCR |
  |---|---|---|
  | 鮮明 | **0.008** | 0.044 |
  | ディザ・低解像度（実ゲーム字幕相当） | 0.123 | **0.017** |

  劣化した映像では RapidOCR が明確に優位です（Windows OCR が `永遠`→`怺遠` のような誤読をする条件で、RapidOCR は正解）。
- **前処理オプション（精度優先）**: ドットフォントや小さい文字向けに、拡大・グレースケール・コントラスト強調(CLAHE)・ノイズ除去・二値化・色反転を選択適用（設定タブ）。速度より精度を優先したいときに有効。
- **日本語校正（非LLM）**: 辞書＋編集距離(RapidFuzz)＋視覚類似字＋**単語バイグラム言語モデル(文脈)** で「永速→永遠」「芳働→労働」「永満→永遠」等の誤認識を補正。設定で **オフ / 候補提示（非破壊）/ 自動修正** を切替。候補提示では該当行を強調し、候補ボタンで採用。正しい語（辞書内）は変更しません。
  - 文脈モデルは Tatoeba 日本語コーパス(約25万文, CC-BY)を Sudachi で解析して構築した単語バイグラム(同梱, 1.1MB)。「永遠に」のような自然な繋がりを優先し、視覚類似だけでは選べない誤りを解消します。
- **多数決OCR（精度優先・低速）**: 前処理条件（拡大率・二値化・反転）を変えて複数回OCRし、文字単位の多数決＋辞書尤度で統合。劣化画像・ディザ字幕に有効。設定タブで有効化。
- **半角スペース除去**: OCRが挿入しがちな不要な半角スペースを取り込み時に一括除去（設定タブ）。
- OCRは常に別プロセス（`ProcessPoolExecutor`）で実行し、UIをブロックしません。

## 必要環境

- Windows 10/11、Python 3.14（3.10+ で動作見込み）
- **Windows OCR 日本語言語パック**（未導入だと起動時に案内が表示されます）
  - 設定 → 時刻と言語 → 言語と地域 → 日本語 → オプション → 「基本入力」をインストール

## セットアップ

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## 使い方

1. 左パネル「入力ソース」でデスクトップ / メディアを選択。
2. **デスクトップ**: 「画面切り取り」または `Ctrl+Alt+O` → 範囲をドラッグ →
   モード（クリップボード / 即リスト / 数字キー待機）に従って処理。
3. **メディア**: ファイルを開く（またはD&D） → 映像上をドラッグして読み取り領域を指定 →
   再生し、`1`〜`9` キーで話者を選んで読み取り（通常 / 連続モードは左パネルで選択）。
   - 領域はドラッグで指定。**ドラッグせずクリックすると領域選択をキャンセル**（解除）します。
4. 右側のリストで話者（プルダウン）・テキスト（ダブルクリックで編集）を調整。
5. 「CSVエクスポート」/「TXTエクスポート」で保存。動画由来の行は時刻列も出力されます。

出力形式:

```
"話者","台詞"            # 画像/デスクトップ
"話者","台詞","MM:SS.mmm" # 動画（時刻付き）
```

## 設定（config.json）

設定は実行ファイル（ソース実行時はプロジェクトルート）と同じ階層の `config.json` に保存されます。
このファイルは個人設定のためリポジトリでは追跡していません。初期値は [`config.example.json`](config.example.json) を参照してください（存在しない場合は既定値で自動生成されます）。

> 実行ファイルの場所に書き込めない場合（`Program Files` 配下、読み取り専用メディア、ウイルス対策ソフトの「フォルダーアクセスの制御」配下など）は、`%LOCALAPPDATA%\RecoOCR` に自動的に退避して保存します。どちらにも書き込めない場合は警告ダイアログを表示します（書き起こしが失われないよう、こまめなエクスポートを推奨）。

| キー | 説明 |
|---|---|
| `characters` | 1〜9キーと話者名の対応 |
| `ocr_engine` | `rapidocr`（推奨）/ `rapidocr:medium` / `windows` / `easyocr` |
| `ocr_lang` | `ja` / `en` |
| `preprocess` | OCR前処理（`enabled`, `upscale`, `grayscale`, `denoise`, `contrast`, `binarize`, `invert`）|
| `multi_ocr_vote` | 多数決OCR（`true` で複数条件の認識結果を統合・低速）|
| `remove_spaces` | 認識結果の半角スペースを除去（`true` / `false`）|
| `correction_mode` | 日本語校正: `off` / `suggest`（候補提示）/ `auto`（自動修正）|
| `ocr_mode` | デスクトップOCR完了時: `clipboard` / `direct` / `numkey` |
| `input_mode` | `desktop` / `media` |
| `read_mode` | メディア: `normal` / `continuous` |
| `shortcut_key` | デスクトップ切り取りのホットキー（pynput 形式） |

設定タブからも編集・保存できます。

## EXE 化

**必ず venv の python を明示指定して実行してください**（`python` だけだと Microsoft Store 版が使われ、`[Errno 2] No such file or directory` になります）:

```powershell
venv\Scripts\python.exe -m pip install pyinstaller
venv\Scripts\python.exe build_exe.py    # -> dist/RecoOCR/RecoOCR.exe
```

- 既定は **Windows OCR 版**（約 470MB、torch 非同梱で軽量・安定）。同梱される `config.json` は開発環境の設定ではなく**アプリの初期設定から生成**されます（EasyOCR 非同梱ビルドでは `ocr_engine` は `windows`）。
- **EasyOCR も同梱したい場合**（torch 込みで数 GB・ビルドに時間がかかります）:

  ```powershell
  venv\Scripts\python.exe build_exe.py --with-easyocr
  ```

- 生成物は `dist/RecoOCR/` フォルダごと配布します（`RecoOCR.exe` と `config.json`、依存一式が入っています）。実行先の PC でも **Windows OCR の日本語言語パック**が必要です。

> `[Errno 2] No such file or directory` が出る場合は、`python` ではなく `venv\Scripts\python.exe` を使っているか確認してください。venv の python は実体パスなので subprocess から正しく起動できます。

## 構成

```
main.py                エントリポイント
app/
  main_window.py       UI司令塔・モード制御・キー処理
  config_manager.py    設定の読み書き
  ocr/                 base(IF) / windows_ocr / easyocr_engine / preprocess / vote / ocr_worker(別プロセス)
  correction/          corrector（校正）/ visual（類似字）/ lm（バイグラム）/ data（同梱モデル）
  capture/             desktop_capture（デスクトップ矩形選択）
  media/               media_player_widget / region_overlay / frame_grabber
  widgets/             transcript_table / settings_panel / correction_panel
  models/              transcript_model
  export/              exporter（CSV/TXT）
```

## ライセンス

本ソフトウェアは [MIT License](LICENSE) で提供されます。

### 第三者のソフトウェア・データ

同梱・依存する主なコンポーネントと、その提供元・ライセンスは次のとおりです。

| コンポーネント | 用途 | ライセンス |
|---|---|---|
| [Tatoeba](https://tatoeba.org/) 日本語文コーパス | 同梱バイグラムモデル `app/correction/data/jp_bigram.json.gz` の生成元 | CC BY 2.0 FR |
| [SudachiPy / SudachiDict](https://github.com/WorksApplications/SudachiPy) | 形態素解析・辞書 | Apache License 2.0 |
| [wordfreq](https://github.com/rspeer/wordfreq) | 語彙頻度辞書 | MIT / データは各出典に従う |
| [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz) | 編集距離・候補検索 | MIT |
| [PySide6 (Qt for Python)](https://www.qt.io/qt-for-python) | GUI | LGPLv3 |
| [PyWinRT (winrt-*)](https://github.com/pywinrt/pywinrt) | Windows OCR 呼び出し | MIT |
| [pynput](https://github.com/moses-palmer/pynput) | グローバルホットキー | LGPLv3 |
| [Pillow](https://python-pillow.org/) / [NumPy](https://numpy.org/) | 画像処理・数値計算 | MIT-CMU / BSD |
| [RapidOCR](https://github.com/RapidAI/RapidOCR) / [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) モデル | OCRエンジン（PP-OCR の ONNX 実行） | Apache License 2.0 |
| [ONNX Runtime](https://onnxruntime.ai/) | 推論エンジン | MIT |
| [EasyOCR](https://github.com/JaidedAI/EasyOCR)（任意） | 代替OCRエンジン | Apache License 2.0 |
| [OpenCV](https://opencv.org/)（任意） | 前処理の高品質化 | Apache License 2.0 |

同梱の `jp_bigram.json.gz` は Tatoeba Project の日本語文（CC BY 2.0 FR）から統計量（単語ユニグラム／バイグラム頻度）を抽出した派生物です。原文そのものは含みません。

Windows OCR（`Windows.Media.Ocr`）は OS の機能であり、利用には Windows と日本語言語パックが必要です。バイナリを再配布する場合は、上記の各ライセンス条項（特に LGPL コンポーネントの条件）をご確認ください。
