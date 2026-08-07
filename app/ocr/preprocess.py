"""OCR 前処理（精度優先オプション）。

PNG バイト列を受け取り、選択された前処理を適用して PNG バイト列で返す。
ワーカープロセス内で呼ぶ想定（UI をブロックしない）。cv2 があれば高品質処理、
無ければ Pillow でフォールバックする。

options（dict）の想定キー:
    enabled   : bool   前処理を行うか
    upscale   : int    拡大率（1/2/3）。小さい/ドットフォントに有効
    grayscale : bool   グレースケール化
    denoise   : bool   ノイズ除去
    contrast  : bool   コントラスト強調（CLAHE / autocontrast）
    binarize  : bool   二値化（Otsu）
    invert    : bool   色反転（暗背景に明るい文字のとき有効なことがある）
"""
from io import BytesIO

try:
    import cv2
    import numpy as np
    _CV2 = True
except Exception:  # pragma: no cover
    _CV2 = False


def _needs_gray(o: dict) -> bool:
    return bool(o.get("grayscale") or o.get("contrast") or o.get("denoise") or o.get("binarize"))


def _apply_cv2(data: bytes, o: dict) -> bytes:
    buf = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        return data

    scale = int(o.get("upscale", 1) or 1)
    if scale > 1:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    work = None  # グレースケール処理系
    if _needs_gray(o):
        work = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if o.get("denoise"):
            work = cv2.fastNlMeansDenoising(work, None, h=10, templateWindowSize=7, searchWindowSize=21)
        if o.get("contrast"):
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            work = clahe.apply(work)
        if o.get("binarize"):
            _, work = cv2.threshold(work, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

    out = work if work is not None else img
    if o.get("invert"):
        out = cv2.bitwise_not(out)

    ok, enc = cv2.imencode(".png", out)
    return enc.tobytes() if ok else data


def _apply_pil(data: bytes, o: dict) -> bytes:
    from PIL import Image, ImageOps, ImageFilter
    im = Image.open(BytesIO(data)).convert("RGB")

    scale = int(o.get("upscale", 1) or 1)
    if scale > 1:
        im = im.resize((im.width * scale, im.height * scale), Image.LANCZOS)
    if _needs_gray(o):
        im = ImageOps.grayscale(im)
        if o.get("denoise"):
            im = im.filter(ImageFilter.MedianFilter(size=3))
        if o.get("contrast"):
            im = ImageOps.autocontrast(im)
        if o.get("binarize"):
            im = im.point(lambda p: 255 if p > 128 else 0, mode="L")
    if o.get("invert"):
        im = ImageOps.invert(im.convert("RGB") if im.mode not in ("L", "RGB") else im)
    out = BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


def apply(data: bytes, options: dict | None) -> bytes:
    """前処理を適用。無効/未指定ならそのまま返す。例外時も原画像を返す。"""
    if not options or not options.get("enabled"):
        return data
    try:
        return _apply_cv2(data, options) if _CV2 else _apply_pil(data, options)
    except Exception as e:
        print(f"[preprocess] error: {e}")
        return data
