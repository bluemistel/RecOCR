"""ダークテーマ（配色・書体・スタイルシート）。

方向性は「管制室」。深いチャコールを地にして情報量を落ち着かせ、
操作の焦点（話者キー・実行ボタン）にだけ琥珀のアクセントを当てる。
時刻（ブックマーク）はシアンで別系統として区別する。

書体は日本語グリフを持つものに限定し、UI と数値で使い分ける:
  - UI      : Yu Gothic UI / Meiryo UI（読みやすい日本語 UI 書体）
  - 数値/キー: Cascadia Mono / Consolas（等幅で桁が揃う）
"""

# --- パレット ---------------------------------------------------------
BG_BASE = "#14161a"      # 最背面
BG_PANEL = "#1b1e24"     # パネル
BG_ELEVATED = "#22262e"  # 一段手前（入力欄・カード）
BG_HOVER = "#2a2f38"
BORDER = "#2e333d"
BORDER_STRONG = "#3c434f"

TEXT = "#e8eaed"
TEXT_DIM = "#9aa2ae"
TEXT_MUTED = "#6b7280"

ACCENT = "#f5b642"       # 琥珀: 主操作・アクティブ
ACCENT_DIM = "#8a6520"
ACCENT_TEXT = "#14161a"  # 琥珀の上に載せる文字

CYAN = "#4FD6FF"         # 時刻（ブックマーク）
SUCCESS = "#5ec27a"
WARN = "#e0a030"
DANGER = "#e5534b"

FLAG_BG = "#3a3222"      # 校正候補ありの行（暗所で見える琥珀寄りの地）
FLAG_TEXT = "#f0d9a0"
SEGMENT_ON_BG = "#2b2820"  # 選択中セグメントの淡い地

FONT_UI = '"Yu Gothic UI", "Meiryo UI", "Segoe UI", sans-serif'
FONT_MONO = '"Cascadia Mono", "Consolas", "MS Gothic", monospace'


def palette():
    """Fusion スタイル用のダークパレット。

    チェックマークやラジオの点は Fusion に描かせる（スタイルシートで
    ::indicator を潰すとチェック記号が消えて状態が読めなくなるため）。
    """
    from PySide6.QtGui import QPalette, QColor
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(BG_BASE))
    p.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    p.setColor(QPalette.ColorRole.Base, QColor(BG_PANEL))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(BG_ELEVATED))
    p.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    p.setColor(QPalette.ColorRole.Button, QColor(BG_ELEVATED))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    p.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(ACCENT_TEXT))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(BG_ELEVATED))
    p.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor(TEXT_MUTED))
    dis = QPalette.ColorGroup.Disabled
    p.setColor(dis, QPalette.ColorRole.Text, QColor(TEXT_MUTED))
    p.setColor(dis, QPalette.ColorRole.ButtonText, QColor(TEXT_MUTED))
    p.setColor(dis, QPalette.ColorRole.WindowText, QColor(TEXT_MUTED))
    return p


def stylesheet() -> str:
    return f"""
QWidget {{
    background-color: {BG_BASE};
    color: {TEXT};
    font-family: {FONT_UI};
    font-size: 13px;
}}
QMainWindow, QDialog {{ background-color: {BG_BASE}; }}

/* --- タブ --- */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background: {BG_PANEL};
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_DIM};
    padding: 8px 18px;
    margin-right: 2px;
    border: 1px solid transparent;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: 600;
}}
QTabBar::tab:selected {{
    background: {BG_PANEL};
    color: {ACCENT};
    border-color: {BORDER};
    border-bottom-color: {BG_PANEL};
}}
QTabBar::tab:hover:!selected {{ color: {TEXT}; }}

/* --- グループ --- */
QGroupBox {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 14px;
    padding: 10px 10px 8px 10px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {TEXT_DIM};
    font-size: 12px;
    letter-spacing: 1px;
}}

/* --- ボタン --- */
QPushButton {{
    background: {BG_ELEVATED};
    color: {TEXT};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    padding: 7px 14px;
    min-height: 18px;
}}
QPushButton:hover {{ background: {BG_HOVER}; border-color: {ACCENT_DIM}; }}
QPushButton:pressed {{ background: {BORDER}; }}
QPushButton:disabled {{ color: {TEXT_MUTED}; border-color: {BORDER}; }}
QPushButton[accent="true"] {{
    background: {ACCENT};
    color: {ACCENT_TEXT};
    border: none;
    font-weight: 700;
}}
QPushButton[accent="true"]:hover {{ background: #ffc95c; }}
QPushButton[accent="true"]:pressed {{ background: #d99e2e; }}
QPushButton[danger="true"] {{ color: {DANGER}; font-weight: 700; }}

/* セグメント（モード切替）
   選択状態は「琥珀の縁と文字＋淡い地」で示す。主操作ボタン（塗りつぶしの琥珀）と
   同じ強さにすると視線の優先順位が崩れるため、あえて一段弱くする。 */
QPushButton[segment="true"] {{
    background: {BG_ELEVATED};
    border: 1px solid {BORDER_STRONG};
    border-left: 3px solid {BORDER_STRONG};
    border-radius: 6px;
    padding: 8px 10px;
    color: {TEXT_DIM};
    text-align: left;
}}
QPushButton[segment="true"]:checked {{
    background: {SEGMENT_ON_BG};
    color: {ACCENT};
    border-color: {ACCENT_DIM};
    border-left: 3px solid {ACCENT};
    font-weight: 700;
}}
QPushButton[segment="true"]:hover:!checked {{ background: {BG_HOVER}; color: {TEXT}; }}

/* 行削除ボタン（小さい固定サイズなので padding を打ち消す） */
QPushButton[rowdelete="true"] {{
    background: transparent;
    border: none;
    padding: 0;
    margin: 0;
    color: {TEXT_MUTED};
    font-size: 16px;
    font-weight: 700;
}}
QPushButton[rowdelete="true"]:hover {{ color: {DANGER}; background: {BG_HOVER};
    border-radius: 4px; }}

/* --- 入力系 --- */
QLineEdit, QComboBox, QSpinBox {{
    background: {BG_ELEVATED};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: {ACCENT_DIM};
}}
QLineEdit:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background: {BG_ELEVATED};
    border: 1px solid {BORDER_STRONG};
    selection-background-color: {ACCENT_DIM};
    selection-color: {TEXT};
    outline: none;
}}

/* チェック/ラジオの指示子は Fusion に描かせる（チェック記号を残すため）。
   ここでは間隔だけ整える。QLabel/QCheckBox は QFrame 派生なので、
   枠が回り込まないよう明示的に打ち消す。 */
QCheckBox, QRadioButton {{ spacing: 8px; padding: 3px 0; background: transparent; }}
QLabel {{ background: transparent; border: none; }}

/* チェック/ラジオの指示子。Fusion 既定は暗い地に沈んで未選択が見えないため、
   「枠のみ＝オフ / 琥珀で塗り＝オン」で明示的に描き分ける。 */
QCheckBox::indicator, QRadioButton::indicator {{
    width: 15px; height: 15px;
    background: {BG_BASE};
    border: 1px solid {TEXT_MUTED};
}}
QCheckBox::indicator {{ border-radius: 3px; }}
QRadioButton::indicator {{ border-radius: 8px; }}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {ACCENT};
    border: 4px solid {BG_BASE};
    outline: 1px solid {ACCENT};
}}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
    border-color: {BORDER_STRONG};
}}

/* --- テーブル --- */
QTableWidget {{
    background: {BG_PANEL};
    alternate-background-color: {BG_ELEVATED};
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: {BORDER};
    selection-background-color: {ACCENT_DIM};
    selection-color: {TEXT};
}}
QHeaderView::section {{
    background: {BG_ELEVATED};
    color: {TEXT_DIM};
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    padding: 6px 8px;
    font-size: 12px;
    font-weight: 600;
}}
QTableWidget QLineEdit {{ border-radius: 3px; padding: 2px 4px; }}

/* --- スクロール --- */
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER_STRONG}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {TEXT_MUTED}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {BORDER_STRONG}; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* --- スライダー（シーク） --- */
QSlider::groove:horizontal {{
    height: 4px; background: {BORDER}; border-radius: 2px;
}}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: {TEXT}; width: 12px; height: 12px;
    margin: -5px 0; border-radius: 6px;
}}
QSlider::handle:horizontal:hover {{ background: {ACCENT}; }}

/* --- スプリッター --- */
QSplitter::handle {{ background: {BORDER}; }}
QSplitter::handle:horizontal {{ width: 4px; }}
QSplitter::handle:vertical {{ height: 4px; }}
QSplitter::handle:hover {{ background: {ACCENT_DIM}; }}

QToolTip {{
    background: {BG_ELEVATED};
    color: {TEXT};
    border: 1px solid {BORDER_STRONG};
    padding: 5px 8px;
    border-radius: 4px;
}}
/* カード（objectName で限定する。プロパティセレクタは QLabel など
   QFrame 派生の子まで巻き込むことがあるため使わない） */
QFrame#card {{
    background: {BG_ELEVATED};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
"""
