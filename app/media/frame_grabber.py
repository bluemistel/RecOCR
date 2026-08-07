"""表示ウィジェット座標の選択矩形を、実フレーム画像の座標へ写像して切り出す。

動画/画像はレターボックス（アスペクト比維持でフィット）表示されるため、
ウィジェット座標 → 画像座標の変換にはスケールとオフセットの補正が要る。
"""
from PySide6.QtCore import QRect, QRectF
from PySide6.QtGui import QImage


def fitted_target_rect(image_size, widget_w: int, widget_h: int) -> QRectF:
    """widget 内にアスペクト比維持で image を収めたときの描画矩形（logical 座標）。"""
    iw, ih = image_size.width(), image_size.height()
    if iw <= 0 or ih <= 0 or widget_w <= 0 or widget_h <= 0:
        return QRectF(0, 0, widget_w, widget_h)
    scale = min(widget_w / iw, widget_h / ih)
    tw, th = iw * scale, ih * scale
    tx, ty = (widget_w - tw) / 2.0, (widget_h - th) / 2.0
    return QRectF(tx, ty, tw, th)


def widget_rect_to_image_rect(sel: QRect, image: QImage,
                              widget_w: int, widget_h: int) -> QRect:
    """選択矩形（ウィジェット座標）→ 画像ピクセル座標へ変換しクランプ。"""
    target = fitted_target_rect(image.size(), widget_w, widget_h)
    if target.width() <= 0 or target.height() <= 0:
        return QRect()
    sx = image.width() / target.width()
    sy = image.height() / target.height()
    ix = (sel.x() - target.x()) * sx
    iy = (sel.y() - target.y()) * sy
    iw = sel.width() * sx
    ih = sel.height() * sy
    # クランプ
    x0 = max(0, int(round(ix)))
    y0 = max(0, int(round(iy)))
    x1 = min(image.width(), int(round(ix + iw)))
    y1 = min(image.height(), int(round(iy + ih)))
    if x1 <= x0 or y1 <= y0:
        return QRect()
    return QRect(x0, y0, x1 - x0, y1 - y0)


def crop(image: QImage, sel: QRect | None, widget_w: int, widget_h: int) -> QImage:
    """選択矩形で画像を切り出す。sel が None なら全体を返す。"""
    if image is None or image.isNull():
        return QImage()
    if sel is None:
        return image
    img_rect = widget_rect_to_image_rect(sel, image, widget_w, widget_h)
    if img_rect.isNull():
        return image
    return image.copy(img_rect)
