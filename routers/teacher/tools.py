"""Teacher Tools router — document and text utilities."""
import logging
from io import BytesIO
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from dependencies import get_template_context, require_login
from rate_limit import limiter

log = logging.getLogger("teacher.tools")
router = APIRouter(prefix="/teacher", dependencies=[Depends(require_login)])
templates = Jinja2Templates(directory="templates")

_MAX_CONV_SIZE = 15 * 1024 * 1024   # 15 MB
_MAX_PDF_SIZE  = 10 * 1024 * 1024   # 10 MB per file
_MAX_IMG_SIZE  =  8 * 1024 * 1024   # 8 MB per image
_MAX_PDF_FILES = 10
_MAX_IMG_FILES = 20

_MAX_FC_SIZE = 50 * 1024 * 1024  # 50 MB

_IMG_EXTS = {'jpg', 'jpeg', 'png', 'webp', 'bmp'}

_FC_MAP = {
    'docx': ['pdf', 'txt'],
    'pdf':  ['docx', 'txt'],
    'txt':  ['pdf', 'docx'],
    'xlsx': ['csv'],
    'csv':  ['xlsx'],
    'jpg':  ['png', 'webp', 'bmp', 'pdf'],
    'jpeg': ['png', 'webp', 'bmp', 'pdf'],
    'png':  ['jpg', 'webp', 'bmp', 'pdf'],
    'webp': ['jpg', 'png', 'bmp'],
    'bmp':  ['jpg', 'png', 'webp'],
    'pptx': ['pdf'],
    'odt':  ['pdf', 'docx'],
    'ods':  ['xlsx', 'csv'],
    'odp':  ['pdf'],
}

_FC_MIME = {
    'pdf':  'application/pdf',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'csv':  'text/csv; charset=utf-8',
    'txt':  'text/plain; charset=utf-8',
    'jpg':  'image/jpeg',
    'jpeg': 'image/jpeg',
    'png':  'image/png',
    'webp': 'image/webp',
    'bmp':  'image/bmp',
}



@router.get("/tools", response_class=HTMLResponse)
async def teacher_tools_hub(request: Request):
    context = await get_template_context(request)
    return templates.TemplateResponse("teacher/tools/hub.html", context)

@router.get("/tools/script-converter", response_class=HTMLResponse)
async def tools_script_converter(request: Request):
    context = await get_template_context(request)
    return templates.TemplateResponse("teacher/tools/script_converter.html", context)


@router.get("/tools/word-counter", response_class=HTMLResponse)
async def tools_word_counter(request: Request):
    context = await get_template_context(request)
    return templates.TemplateResponse("teacher/tools/word_counter.html", context)


@router.get("/tools/pdf-merge", response_class=HTMLResponse)
async def tools_pdf_merge_page(request: Request):
    context = await get_template_context(request)
    return templates.TemplateResponse("teacher/tools/pdf_merge.html", context)


@router.post("/tools/pdf-merge")
@limiter.limit("10/minute")
async def tools_pdf_merge(
    request: Request,
    files: List[UploadFile] = File(...),
):
    if len(files) < 2:
        raise HTTPException(400, detail="Kamida 2 ta PDF fayl kerak.")
    if len(files) > _MAX_PDF_FILES:
        raise HTTPException(400, detail=f"Maksimal {_MAX_PDF_FILES} ta fayl.")

    raw_files: list[bytes] = []
    for f in files:
        if not f.filename.lower().endswith(".pdf"):
            raise HTTPException(400, detail=f"Faqat PDF fayllar: {f.filename}")
        data = await f.read()
        if len(data) > _MAX_PDF_SIZE:
            raise HTTPException(400, detail=f"Fayl hajmi 10 MB dan oshmasligi kerak: {f.filename}")
        raw_files.append(data)

    merged = await run_in_threadpool(_merge_pdfs, raw_files)
    return StreamingResponse(
        BytesIO(merged), media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="merged.pdf"',
                 "Content-Length": str(len(merged))},
    )


@router.get("/tools/image-to-pdf", response_class=HTMLResponse)
async def tools_image_to_pdf_page(request: Request):
    context = await get_template_context(request)
    return templates.TemplateResponse("teacher/tools/image_to_pdf.html", context)


@router.post("/tools/image-to-pdf")
@limiter.limit("10/minute")
async def tools_image_to_pdf(
    request: Request,
    files: List[UploadFile] = File(...),
):
    _ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}
    if not files:
        raise HTTPException(400, detail="Rasm yuklanmadi.")
    if len(files) > _MAX_IMG_FILES:
        raise HTTPException(400, detail=f"Maksimal {_MAX_IMG_FILES} ta rasm.")

    raw_files: list[bytes] = []
    for f in files:
        ext = ("." + f.filename.rsplit(".", 1)[-1].lower()) if "." in f.filename else ""
        if ext not in _ALLOWED_EXT:
            raise HTTPException(400, detail=f"Qo'llab-quvvatlanmaydigan format: {f.filename}")
        data = await f.read()
        if len(data) > _MAX_IMG_SIZE:
            raise HTTPException(400, detail="Rasm hajmi 8 MB dan oshmasligi kerak.")
        raw_files.append(data)

    pdf_bytes = await run_in_threadpool(_images_to_pdf, raw_files)
    return StreamingResponse(
        BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="images.pdf"',
                 "Content-Length": str(len(pdf_bytes))},
    )


@router.get("/tools/qr", response_class=HTMLResponse)
async def tools_qr_page(request: Request):
    context = await get_template_context(request)
    return templates.TemplateResponse("teacher/tools/qr.html", context)


@router.post("/tools/qr")
@limiter.limit("30/minute")
async def tools_qr_generate(
    request: Request,
    text: str = Form(...),
    size: int = Form(300),
    fg_color: str = Form("#000000"),
    bg_color: str = Form("#ffffff"),
    error_level: str = Form("M"),
):
    text = text.strip()
    if not text:
        raise HTTPException(400, detail="Matn bo'sh bo'lmasligi kerak.")
    if len(text) > 2000:
        raise HTTPException(400, detail="Matn 2000 ta belgidan oshmasligi kerak.")
    size = max(100, min(800, size))
    error_level = error_level.upper() if error_level.upper() in ("L", "M", "Q", "H") else "M"
    import re as _re
    if not _re.match(r'^#[0-9a-fA-F]{6}$', fg_color): fg_color = "#000000"
    if not _re.match(r'^#[0-9a-fA-F]{6}$', bg_color): bg_color = "#ffffff"

    img_bytes = await run_in_threadpool(_make_qr, text, size, fg_color, bg_color, error_level)
    return StreamingResponse(
        BytesIO(img_bytes), media_type="image/png",
        headers={"Content-Length": str(len(img_bytes))},
    )


def _merge_pdfs(raw_files: list) -> bytes:
    from pypdf import PdfWriter, PdfReader
    writer = PdfWriter()
    for data in raw_files:
        reader = PdfReader(BytesIO(data))
        for page in reader.pages:
            writer.add_page(page)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def _images_to_pdf(raw_files: list) -> bytes:
    from PIL import Image
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import inch
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as rl_canvas

    page_w, page_h = A4
    margin = 0.3 * inch
    usable_w = page_w - 2 * margin
    usable_h = page_h - 2 * margin

    out = BytesIO()
    c = rl_canvas.Canvas(out, pagesize=A4)

    for i, img_data in enumerate(raw_files):
        img = Image.open(BytesIO(img_data))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        iw, ih = img.size
        ratio = min(usable_w / iw, usable_h / ih)
        rw, rh = iw * ratio, ih * ratio
        x = margin + (usable_w - rw) / 2
        y = margin + (usable_h - rh) / 2
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)
        buf.seek(0)
        c.drawImage(ImageReader(buf), x, y, width=rw, height=rh)
        if i < len(raw_files) - 1:
            c.showPage()

    c.save()
    return out.getvalue()


def _make_qr(text: str, size: int,
              fg_color: str = "#000000",
              bg_color: str = "#ffffff",
              error_level: str = "M") -> bytes:
    import qrcode
    import qrcode.constants
    _ec_map = {
        "L": qrcode.constants.ERROR_CORRECT_L,
        "M": qrcode.constants.ERROR_CORRECT_M,
        "Q": qrcode.constants.ERROR_CORRECT_Q,
        "H": qrcode.constants.ERROR_CORRECT_H,
    }
    ec = _ec_map.get(error_level, qrcode.constants.ERROR_CORRECT_M)
    qr = qrcode.QRCode(
        error_correction=ec,
        box_size=max(1, size // 25),
        border=4,
    )
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color=fg_color, back_color=bg_color)
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


import re as _re_conv

_KL_MULTI = [
    ('Нг','Ng'),('нг','ng'),('Ш','Sh'),('ш','sh'),('Ч','Ch'),('ч','ch'),
    ('Ю','Yu'),('ю','yu'),('Я','Ya'),('я','ya'),('Ё','Yo'),('ё','yo'),
    ('Е','Ye'),('е','ye'),('Ж','J'),('ж','j'),('Ц','Ts'),('ц','ts'),
    ('Щ','Sh'),('щ','sh'),('Ъ','ʼ'),('ъ','ʼ'),('Ь',''),('ь',''),
    ('Ы','I'),('ы','i'),
]
_KL_SINGLE = {
    'А':'A','а':'a','Б':'B','б':'b','В':'V','в':'v','Г':'G','г':'g',
    'Д':'D','д':'d','З':'Z','з':'z','И':'I','и':'i','Й':'Y','й':'y',
    'К':'K','к':'k','Л':'L','л':'l','М':'M','м':'m','Н':'N','н':'n',
    'О':'O','о':'o','П':'P','п':'p','Р':'R','р':'r','С':'S','с':'s',
    'Т':'T','т':'t','У':'U','у':'u','Ф':'F','ф':'f','Х':'X','х':'x',
    'Э':'E','э':'e','Ҳ':'H','ҳ':'h','Қ':'Q','қ':'q',
    'Ғ':'Gʻ','ғ':'gʻ','Ў':'Oʻ','ў':'oʻ',
}
_LK_MULTI_RE = [
    (_re_conv.compile("O[\u02BB\u02BC\u2018\u2019']"), 'Ў'),
    (_re_conv.compile("o[\u02BB\u02BC\u2018\u2019']"), 'ў'),
    (_re_conv.compile("G[\u02BB\u02BC\u2018\u2019']"), 'Ғ'),
    (_re_conv.compile("g[\u02BB\u02BC\u2018\u2019']"), 'ғ'),
    (_re_conv.compile(r'Ng'), 'Нг'),
    (_re_conv.compile(r'ng'), 'нг'),
    (_re_conv.compile(r'NG'), 'НГ'),
    (_re_conv.compile(r'Sh'), 'Ш'),
    (_re_conv.compile(r'sh'), 'ш'),
    (_re_conv.compile(r'SH'), 'Ш'),
    (_re_conv.compile(r'Ch'), 'Ч'),
    (_re_conv.compile(r'ch'), 'ч'),
    (_re_conv.compile(r'CH'), 'Ч'),
    (_re_conv.compile(r'Ts'), 'Ц'),
    (_re_conv.compile(r'ts'), 'ц'),
    (_re_conv.compile(r'TS'), 'Ц'),
    (_re_conv.compile(r'Ye'), 'Е'),
    (_re_conv.compile(r'ye'), 'е'),
    (_re_conv.compile(r'YE'), 'Е'),
    (_re_conv.compile(r'Yo'), 'Ё'),
    (_re_conv.compile(r'yo'), 'ё'),
    (_re_conv.compile(r'YO'), 'Ё'),
    (_re_conv.compile(r'Yu'), 'Ю'),
    (_re_conv.compile(r'yu'), 'ю'),
    (_re_conv.compile(r'YU'), 'Ю'),
    (_re_conv.compile(r'Ya'), 'Я'),
    (_re_conv.compile(r'ya'), 'я'),
    (_re_conv.compile(r'YA'), 'Я'),
    (_re_conv.compile("[\u02BC\u02BB\u2019]"), 'ъ'),
]
_LK_SINGLE = {
    'A':'А','a':'а','B':'Б','b':'б','V':'В','v':'в','G':'Г','g':'г',
    'D':'Д','d':'д','E':'Е','e':'е','Z':'З','z':'з','I':'И','i':'и',
    'Y':'Й','y':'й','J':'Ж','j':'ж','K':'К','k':'к','L':'Л','l':'л',
    'M':'М','m':'м','N':'Н','n':'н','O':'О','o':'о','P':'П','p':'п',
    'R':'Р','r':'р','S':'С','s':'с','T':'Т','t':'т','U':'У','u':'у',
    'F':'Ф','f':'ф','X':'Х','x':'х','H':'Ҳ','h':'ҳ','Q':'Қ','q':'қ',
}


def _py_k2l(text: str) -> str:
    for k, v in _KL_MULTI:
        text = text.replace(k, v)
    return ''.join(_KL_SINGLE.get(ch, ch) for ch in text)


def _py_l2k(text: str) -> str:
    for pattern, repl in _LK_MULTI_RE:
        text = pattern.sub(repl, text)
    return ''.join(_LK_SINGLE.get(ch, ch) for ch in text)


def _do_convert_txt(data: bytes, mode: str) -> bytes:
    fn = _py_k2l if mode == "k2l" else _py_l2k
    for enc in ("utf-8-sig", "utf-8", "cp1251", "iso-8859-5", "latin-1"):
        try:
            text = data.decode(enc)
            if enc == "utf-8" and text.count("�") > len(text) * 0.05:
                continue  
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        text = data.decode("utf-8", errors="replace")
    return fn(text).encode("utf-8")


def _do_convert_docx(data: bytes, mode: str) -> bytes:
    from docx import Document
    fn = _py_k2l if mode == "k2l" else _py_l2k

    def _conv_para(para):
        for run in para.runs:
            if run.text:
                run.text = fn(run.text)

    doc = Document(BytesIO(data))

    for para in doc.paragraphs:
        _conv_para(para)

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    _conv_para(para)

    for section in doc.sections:
        for para in section.header.paragraphs:
            _conv_para(para)
        for para in section.footer.paragraphs:
            _conv_para(para)

    out = BytesIO()
    doc.save(out)
    return out.getvalue()


def _parse_cmap(cmap_data: bytes):
    """Parse PDF ToUnicode CMap. Returns (glyph_bytes -> char, char -> glyph_bytes)."""
    import re
    g2u, u2g = {}, {}

    def _add(glyph_bytes, unicode_hex):
        h = unicode_hex.decode()
        try:
            if len(h) == 4:
                ch = chr(int(h, 16))
            elif len(h) == 8:
                hi, lo = int(h[:4], 16), int(h[4:], 16)
                ch = chr((hi - 0xD800) * 0x400 + (lo - 0xDC00) + 0x10000)
            else:
                return
            if ch != '\x00':
                g2u[glyph_bytes] = ch
                if ch not in u2g:
                    u2g[ch] = glyph_bytes
        except (ValueError, OverflowError):
            pass

    for sec in re.findall(rb'beginbfchar(.*?)endbfchar', cmap_data, re.DOTALL):
        for src_h, dst_h in re.findall(rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', sec):
            try:
                _add(bytes.fromhex(src_h.decode()), dst_h)
            except Exception:
                pass

    for sec in re.findall(rb'beginbfrange(.*?)endbfrange', cmap_data, re.DOTALL):
        for s0, s1, d0 in re.findall(
                rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', sec):
            try:
                start, end, dst = int(s0, 16), int(s1, 16), int(d0, 16)
                blen = (len(s0) + 1) // 2
                for off in range(end - start + 1):
                    gb = (start + off).to_bytes(blen, 'big')
                    dh = hex(dst + off)[2:].zfill(4).encode()
                    _add(gb, dh)
            except Exception:
                pass

    return g2u, u2g


def _pdf_unescape(s: bytes) -> bytes:
    result, i = bytearray(), 0
    while i < len(s):
        if s[i:i+1] == b'\\':
            c = s[i+1:i+2]
            esc = {b'n': 10, b'r': 13, b't': 9, b'b': 8, b'f': 12,
                   b'(': 40, b')': 41, b'\\': 92}
            if c in esc:
                result.append(esc[c]); i += 2
            elif c and c[0:1] in b'01234567':
                import re
                m = re.match(rb'[0-7]{1,3}', s[i+1:i+4])
                if m:
                    result.append(int(m.group(), 8)); i += 1 + len(m.group())
                else:
                    i += 1
            else:
                i += 1
        else:
            result.append(s[i]); i += 1
    return bytes(result)


def _pdf_escape(data: bytes) -> bytes:
    result = bytearray()
    for b in data:
        if b in (40, 41, 92):
            result.extend(b'\\' + bytes([b]))
        elif b < 32 or b > 126:
            result.extend(f'\\{b:03o}'.encode())
        else:
            result.append(b)
    return bytes(result)


def _do_convert_pdf(data: bytes, mode: str):
    """
    Multi-phase PDF script conversion — style-preserving throughout.

    Phase 1: CMap in-place  — modern PDFs with ToUnicode CMap tables.
    Phase 2: Raw cp1251 stream patching — legacy Uzbek/Russian PDFs.
    Phase 3: Raw cp866 stream patching  — older DOS-era Cyrillic PDFs.

    All phases edit only the text bytes inside content streams; the rest of
    the PDF (fonts, images, colours, layout, metadata) is never touched.
    Returns (pdf_bytes, n_conversions).  Returns (data, 0) when conversion
    is not possible so the caller can show a meaningful error.
    """
    import re
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ArrayObject

    fn = _py_k2l if mode == "k2l" else _py_l2k

    def _get_obj(x):
        return x.get_object() if hasattr(x, 'get_object') else x

    def _parse_enc_diffs(diffs):
        """Parse a /Encoding /Differences array -> (g2u, u2g).
        Entries: [start_byte /uniXXXX /uniXXXX ...]  (PDF spec 9.6.5)."""
        g2u, u2g = {}, {}
        try:
            current = 0
            for item in diffs:
                v = _get_obj(item)
                try:
                    current = int(v); continue
                except (TypeError, ValueError):
                    pass
                name = str(v).lstrip('/')
                ch = None
                if name.startswith('uni') and len(name) >= 7:
                    try: ch = chr(int(name[3:7], 16))
                    except ValueError: pass
                elif name.startswith('u') and 5 <= len(name) <= 6:
                    try: ch = chr(int(name[1:], 16))
                    except ValueError: pass
                if ch and ch != '\x00':
                    gb = bytes([current])
                    g2u[gb] = ch
                    if ch not in u2g:
                        u2g[ch] = gb
                current += 1
        except Exception:
            pass
        return g2u, u2g

    def _apply_to_streams(pdf_data: bytes, conv_fn):
        """
        Walk every page content stream, apply conv_fn(raw_bytes) -> (new_bytes, n).
        Returns (new_pdf_bytes, total_n) or (pdf_data, 0) on failure/no change.
        """
        try:
            r = PdfReader(BytesIO(pdf_data))
            w = PdfWriter()
            w.clone_reader_document_root(r)
            total = 0
            for page in w.pages:
                contents = _get_obj(page.get('/Contents'))
                if contents is None:
                    continue
                if isinstance(contents, ArrayObject):
                    for ref in contents:
                        obj = _get_obj(ref)
                        if hasattr(obj, 'get_data') and hasattr(obj, 'set_data'):
                            try:
                                new_raw, n = conv_fn(obj.get_data())
                                if n > 0:
                                    obj.set_data(new_raw)
                                    total += n
                            except Exception:
                                pass
                elif hasattr(contents, 'get_data') and hasattr(contents, 'set_data'):
                    try:
                        new_raw, n = conv_fn(contents.get_data())
                        if n > 0:
                            contents.set_data(new_raw)
                            total += n
                    except Exception:
                        pass
            if total == 0:
                return pdf_data, 0
            out = BytesIO()
            w.write(out)
            return out.getvalue(), total
        except Exception:
            return pdf_data, 0

    # ── Phase 1: CMap in-place ────────────────────────────────────────────────
    def _build_font_cmaps(page):
        cmaps = {}
        try:
            res = _get_obj(page.get('/Resources'))
            if res is None:
                return cmaps
            fonts = _get_obj(res.get('/Font'))
            if fonts is None:
                return cmaps
            for key in fonts:
                font_obj = _get_obj(fonts[key])
                to_uni = font_obj.get('/ToUnicode')
                g2u, u2g = {}, {}
                if to_uni is not None:
                    try:
                        g2u, u2g = _parse_cmap(_get_obj(to_uni).get_data())
                    except Exception:
                        pass
                if not g2u:
                    try:
                        enc_ref = font_obj.get('/Encoding')
                        if enc_ref is not None:
                            enc_obj = _get_obj(enc_ref)
                            diffs = None
                            if hasattr(enc_obj, 'get'):
                                d = enc_obj.get('/Differences')
                                if d is not None:
                                    diffs = _get_obj(d)
                            if diffs is not None:
                                g2u, u2g = _parse_enc_diffs(diffs)
                    except Exception:
                        pass
                if g2u:
                    cmaps[key.lstrip('/')] = (g2u, u2g)
        except Exception:
            pass
        return cmaps

    def _conv_stream_cmap(raw: bytes, cmaps: dict):
        """Convert text strings using CMap tables. Returns (new_bytes, n_conversions)."""
        _FB = {
            'ʻ': ["'", '\u2018', '\u2019'],
            'ʼ': ["'", '\u2019'],
        }
        result = bytearray()
        i = 0
        cur_font = [None]
        n_conv = [0]

        while i < len(raw):
            m = re.match(rb'/([^\s/\[\]()<>{}]+)\s+[\d.]+\s+Tf', raw[i:])
            if m:
                cur_font[0] = m.group(1).decode('latin-1')
                result.extend(raw[i:i + m.end()])
                i += m.end()
                continue

            if raw[i:i+1] == b'(':
                j, depth = i + 1, 1
                while j < len(raw) and depth > 0:
                    if raw[j] == 92:
                        j += 2
                    elif raw[j] == 40:
                        depth += 1; j += 1
                    elif raw[j] == 41:
                        depth -= 1; j += 1
                    else:
                        j += 1

                font = cur_font[0]
                if font and font in cmaps:
                    g2u, u2g = cmaps[font]
                    raw_str = _pdf_unescape(raw[i+1:j-1])
                    bw = max((len(k) for k in g2u), default=1)
                    decoded, k = [], 0
                    while k < len(raw_str):
                        found = False
                        for width in range(bw, 0, -1):
                            code = raw_str[k:k+width]
                            if code in g2u:
                                decoded.append(g2u[code])
                                k += width
                                found = True
                                break
                        if not found:
                            decoded.append('')
                            k += 1
                    text = ''.join(decoded)
                    converted = fn(text)
                    if converted != text:
                        new_bytes = bytearray()
                        ok = True
                        for ch in converted:
                            code = u2g.get(ch)
                            if code is None:
                                for fb in _FB.get(ch, []):
                                    code = u2g.get(fb)
                                    if code is not None:
                                        break
                            if code is None:
                                ok = False; break
                            new_bytes.extend(code)
                        if ok:
                            result.extend(b'(' + _pdf_escape(bytes(new_bytes)) + b')')
                            n_conv[0] += 1
                            i = j
                            continue

                result.extend(raw[i:j])
                i = j
                continue

            if raw[i:i+1] == b'<' and i + 1 < len(raw) and raw[i+1:i+2] != b'<':
                end = raw.find(b'>', i + 1)
                if end != -1:
                    h = raw[i+1:end]
                    if re.fullmatch(rb'[0-9A-Fa-f]+', h) and len(h) % 4 == 0:
                        font = cur_font[0]
                        if font and font in cmaps:
                            try:
                                text = bytes.fromhex(h.decode()).decode('utf-16-be')
                                converted = fn(text)
                                if converted != text and any('Ѐ' <= c <= 'ӿ' for c in text):
                                    new_h = converted.encode('utf-16-be').hex().upper().encode()
                                    result.extend(b'<' + new_h + b'>')
                                    n_conv[0] += 1
                                    i = end + 1
                                    continue
                            except Exception:
                                pass
                    result.extend(raw[i:end+1])
                    i = end + 1
                    continue

            result.append(raw[i])
            i += 1

        return bytes(result), n_conv[0]
    
    try:
        import pikepdf as _pk1
        _pdf1 = _pk1.open(BytesIO(data))
        _total1 = 0

        def _build_cmaps1(resources):
            """Build glyph↔unicode maps from a /Resources dict (ToUnicode or /Differences)."""
            _cm = {}
            try:
                for _fk in resources.Font.keys():
                    _fo = resources.Font[_fk]
                    _g, _u = {}, {}
                    if '/ToUnicode' in _fo:
                        try:
                            _g, _u = _parse_cmap(_fo['/ToUnicode'].read_bytes())
                        except Exception:
                            pass
                    if not _g:
                        try:
                            _e = _fo.get('/Encoding')
                            if _e is not None:
                                _d = None
                                try:
                                    if hasattr(_e, 'get') and '/Differences' in _e:
                                        _d = list(_e['/Differences'])
                                    elif hasattr(_e, '__iter__') and not isinstance(_e, str):
                                        _d = list(_e)
                                except Exception:
                                    pass
                                if _d:
                                    _g, _u = _parse_enc_diffs(_d)
                        except Exception:
                            pass
                    if _g:
                        _cm[str(_fk).lstrip('/')] = (_g, _u)
            except AttributeError:
                pass
            return _cm

        def _process_content_streams1(streams_obj, cmaps):
            """Convert all streams in a /Contents or a single stream object; return n converted."""
            _n = 0
            _streams = list(streams_obj) if isinstance(streams_obj, _pk1.Array) else [streams_obj]
            for _s in _streams:
                try:
                    _new, _cnt = _conv_stream_cmap(_s.read_bytes(), cmaps)
                    if _cnt > 0:
                        _s.write(_new)
                        _n += _cnt
                except Exception:
                    pass
            return _n

        def _process_xobjects1(resources, depth=0):
            """Recursively process Form XObjects within a /Resources dict; return n converted."""
            if depth > 4:
                return 0
            _n = 0
            try:
                xobjs = resources.get('/XObject')
                if xobjs is None:
                    return 0
                for _xk in xobjs.keys():
                    try:
                        _xo = xobjs[_xk]
                        if str(_xo.get('/Subtype', '')) != '/Form':
                            continue
                        _xo_res = _xo.get('/Resources')
                        if _xo_res is None:
                            continue
                        _xo_cmaps = _build_cmaps1(_xo_res)
                        if _xo_cmaps:
                            try:
                                _new, _cnt = _conv_stream_cmap(_xo.read_bytes(), _xo_cmaps)
                                if _cnt > 0:
                                    _xo.write(_new)
                                    _n += _cnt
                            except Exception:
                                pass
                        _n += _process_xobjects1(_xo_res, depth + 1)
                    except Exception:
                        pass
            except Exception:
                pass
            return _n

        for _pg1 in _pdf1.pages:
            try:
                _pg_res = _pg1.get('/Resources')
                if _pg_res is None:
                    continue

                _cmaps1 = _build_cmaps1(_pg_res)

                _co1 = _pg1.get('/Contents')
                if _co1 is not None and _cmaps1:
                    _total1 += _process_content_streams1(_co1, _cmaps1)

                _total1 += _process_xobjects1(_pg_res)
            except Exception:
                continue
        if _total1 > 0:
            log.info('PDF phase-1: converted %d string(s) in-place', _total1)
            _out1 = BytesIO()
            _pdf1.save(_out1)
            return _out1.getvalue(), _total1
        try:
            for _pgi, _pg_d in enumerate(_pdf1.pages):
                _res_d = _pg_d.get('/Resources')
                if _res_d is None:
                    log.debug('PDF phase-1 diag: page %d has no /Resources', _pgi)
                    continue
                try:
                    _fnames = list(_res_d.Font.keys())
                    log.debug('PDF phase-1 diag: page %d fonts: %s', _pgi, _fnames)
                except AttributeError:
                    log.debug('PDF phase-1 diag: page %d has no /Font', _pgi)
                try:
                    _xnames = list(_res_d['/XObject'].keys())
                    log.debug('PDF phase-1 diag: page %d XObjects: %s', _pgi, _xnames)
                except Exception:
                    pass
        except Exception:
            pass
        log.debug('PDF phase-1: no in-place conversions (chars not in CMap or no CMap fonts)')
    except Exception as _p1_err:
        import traceback
        log.warning('PDF phase-1 failed: %s\n%s', _p1_err, traceback.format_exc())

    # ── Phase 2: CMap decode + DejaVu font substitution ─────────────────────
    # Phase 1 can DECODE text via CMap but cannot RE-ENCODE because the
    # font lacks the target-script glyphs (e.g. a Cyrillic-only font cannot
    # hold Latin output).  Solution: replace the font with DejaVu Sans (which
    # covers both Cyrillic and Latin) and rewrite text strings with the new
    # glyph-byte mapping.  Every other PDF operator is left completely alone.
    try:    
        import pikepdf as _pikepdf
        from reportlab.pdfbase import pdfmetrics as _rl_pm
        from reportlab.pdfbase.ttfonts import TTFont as _rl_TTF
        from reportlab.pdfgen import canvas as _rl_canvas
        import os as _os

        _TTF_VARIANTS = {
            (False, False): '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            (True,  False): '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            (False, True):  '/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf',
            (True,  True):  '/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf',
        }
        _TTF_WIN = {
            (False, False): 'C:/Windows/Fonts/arial.ttf',
            (True,  False): 'C:/Windows/Fonts/arialbd.ttf',
            (False, True):  'C:/Windows/Fonts/ariali.ttf',
            (True,  True):  'C:/Windows/Fonts/arialbi.ttf',
        }
        _TTF_MAC = {
            (False, False): '/Library/Fonts/Arial.ttf',
            (True,  False): '/Library/Fonts/Arial Bold.ttf',
            (False, True):  '/Library/Fonts/Arial Italic.ttf',
            (True,  True):  '/Library/Fonts/Arial Bold Italic.ttf',
        }
        _FB2 = {
            '\u02BB': "'", '\u02BC': "'",
            '\u2018': "'", '\u2019': "'",
            '\u201C': '"', '\u201D': '"',
        }

        _p2_src = _pikepdf.open(BytesIO(data))
        _p2_total = 0
        _p2_subst_ctr = [0]

        for _p2_page in _p2_src.pages:
            _p2_fcmaps  = {}   
            _p2_fstyles = {}  
            try:
                _p2_fonts = _p2_page.Resources.Font
            except AttributeError:
                continue

            for _k in _p2_fonts.keys():
                _fo = _p2_fonts[_k]
                _g2u, _u2g = {}, {}
                if '/ToUnicode' in _fo:
                    try:
                        _g2u, _u2g = _parse_cmap(_fo['/ToUnicode'].read_bytes())
                    except Exception:
                        pass
                if not _g2u:
                    try:
                        _enc = _fo.get('/Encoding')
                        if _enc is not None:
                            _diffs = None
                            try:
                                if hasattr(_enc, 'get') and '/Differences' in _enc:
                                    _diffs = list(_enc['/Differences'])
                                elif hasattr(_enc, '__iter__') and not isinstance(_enc, str):
                                    _diffs = list(_enc)
                            except Exception:
                                pass
                            if _diffs:
                                _cur = 0
                                for _di in _diffs:
                                    try:
                                        _cur = int(_di); continue
                                    except (TypeError, ValueError):
                                        pass
                                    _dn = str(_di).lstrip('/')
                                    _dch = None
                                    if _dn.startswith('uni') and len(_dn) >= 7:
                                        try: _dch = chr(int(_dn[3:7], 16))
                                        except ValueError: pass
                                    elif _dn.startswith('u') and 5 <= len(_dn) <= 6:
                                        try: _dch = chr(int(_dn[1:], 16))
                                        except ValueError: pass
                                    if _dch and _dch != '\x00':
                                        _dgb = bytes([_cur])
                                        _g2u[_dgb] = _dch
                                        if _dch not in _u2g:
                                            _u2g[_dch] = _dgb
                                    _cur += 1
                    except Exception:
                        pass
                if not _g2u:
                    continue
                _ck = str(_k).lstrip('/')
                _p2_fcmaps[_ck] = (_g2u, _u2g)
                _bf = str(_fo.get('/BaseFont', ''))
                _p2_fstyles[_ck] = (
                    any(x in _bf for x in ('Bold', 'bold', 'Heavy', 'Black')),
                    any(x in _bf for x in ('Italic', 'italic', 'Oblique', 'oblique')),
                )

            if not _p2_fcmaps:
                continue

            try:
                _p2_co = _p2_page.get('/Contents')
                if _p2_co is None:
                    continue
                _p2_raw = (
                    b''.join(_o.read_bytes() for _o in _p2_co)
                    if isinstance(_p2_co, _pikepdf.Array)
                    else _p2_co.read_bytes()
                )
            except Exception:
                continue

            _p2_needs   = set()  
            _p2_allch   = {}     
            _p2_cf = [None]
            _p2_ii = 0
            while _p2_ii < len(_p2_raw):
                _mm = re.match(rb'/([^\s/\[\]()<>{}]+)\s+[\d.]+\s+Tf', _p2_raw[_p2_ii:])
                if _mm:
                    _p2_cf[0] = _mm.group(1).decode('latin-1')
                    _p2_ii += _mm.end(); continue
                if _p2_raw[_p2_ii:_p2_ii+1] == b'(':
                    _jj, _dd = _p2_ii + 1, 1
                    while _jj < len(_p2_raw) and _dd > 0:
                        if _p2_raw[_jj] == 92:   _jj += 2
                        elif _p2_raw[_jj] == 40:  _dd += 1; _jj += 1
                        elif _p2_raw[_jj] == 41:  _dd -= 1; _jj += 1
                        else:                      _jj += 1
                    _fk = _p2_cf[0]
                    if _fk and _fk in _p2_fcmaps:
                        _g2u, _u2g = _p2_fcmaps[_fk]
                        _rs  = _pdf_unescape(_p2_raw[_p2_ii+1:_jj-1])
                        _bw  = max((len(_kk) for _kk in _g2u), default=1)
                        _dec, _ki = [], 0
                        while _ki < len(_rs):
                            _hit = False
                            for _w in range(_bw, 0, -1):
                                if _rs[_ki:_ki+_w] in _g2u:
                                    _dec.append(_g2u[_rs[_ki:_ki+_w]])
                                    _ki += _w; _hit = True; break
                            if not _hit: _ki += 1
                        _txt  = ''.join(_dec)
                        _conv = fn(_txt)
                        if _fk not in _p2_allch:
                            _p2_allch[_fk] = set()
                        for _ch in _conv:
                            if _ch: _p2_allch[_fk].add(_ch)
                        if _conv != _txt:
                            for _ch in _conv:
                                if _ch and _u2g.get(_ch) is None:
                                    _p2_needs.add(_fk); break
                    _p2_ii = _jj; continue
                _p2_ii += 1

            if not _p2_needs:
                continue

            _p2_repl = {}   
            for _fk in _p2_needs:
                _style   = _p2_fstyles.get(_fk, (False, False))
                _ttfp    = _TTF_VARIANTS.get(_style) or _TTF_VARIANTS[(False, False)]
                if not _os.path.exists(_ttfp):
                    _ttfp = (_TTF_WIN.get(_style) or _TTF_WIN[(False, False)])
                    if not _os.path.exists(_ttfp):
                        _ttfp = (_TTF_MAC.get(_style) or _TTF_MAC[(False, False)])
                    if not _os.path.exists(_ttfp):
                        _all_candidates = (
                            list(_TTF_VARIANTS.values())
                            + list(_TTF_WIN.values())
                            + list(_TTF_MAC.values())
                        )
                        _ttfp = next((p for p in _all_candidates if _os.path.exists(p)), None)
                    if not _ttfp:
                        log.warning('PDF phase-2: no substitute TTF font found for %s', _fk)
                        continue

                _chars_needed = (_p2_allch.get(_fk) or set()) | {' ', '?'}
                _chars_needed.discard('')
                _char_str = ''.join(sorted(_chars_needed, key=ord))

                try:
                    _rl_id = f'SubstDV_{_p2_subst_ctr[0]}'
                    _p2_subst_ctr[0] += 1
                    if _rl_id not in _rl_pm.getRegisteredFontNames():
                        _rl_pm.registerFont(_rl_TTF(_rl_id, _ttfp))
                    _mb = BytesIO()
                    _mc = _rl_canvas.Canvas(_mb)
                    _mc.setFont(_rl_id, 12)
                    _mc.drawString(10, 700, _char_str)
                    _mc.save(); _mb.seek(0)

                    _mini = _pikepdf.open(_mb)
                    _new_fo = None; _new_u2g = {}
                    for _mk in _mini.pages[0].Resources.Font.keys():
                        _mfo = _mini.pages[0].Resources.Font[_mk]
                        if '+' not in str(_mfo.get('/BaseFont', '')):
                            continue
                        if '/ToUnicode' not in _mfo:
                            continue
                        _, _nu2g = _parse_cmap(_mfo['/ToUnicode'].read_bytes())
                        if _nu2g:
                            _new_fo = _mfo; _new_u2g = _nu2g; break

                    if _new_fo is None:
                        continue

                    _new_key = f'SF{_p2_subst_ctr[0]-1}'
                    _p2_fonts[f'/{_new_key}'] = _p2_src.copy_foreign(_new_fo)
                    _p2_repl[_fk] = (_new_key, _new_u2g, _p2_fcmaps[_fk][0])

                except Exception as _e:
                    log.warning('PDF font-subst failed for %s: %s', _fk, _e)
                    continue

            if not _p2_repl:
                continue

            def _p2_rewrite(raw_b: bytes) -> tuple:
                res = bytearray(); _cf2 = [None]; _n2 = [0]; i2 = 0
                while i2 < len(raw_b):
                    _fm = re.match(rb'/([^\s/\[\]()<>{}]+)(\s+[\d.]+\s+Tf)', raw_b[i2:])
                    if _fm:
                        _fk2 = _fm.group(1).decode('latin-1')
                        _cf2[0] = _fk2
                        if _fk2 in _p2_repl:
                            res.extend(b'/' + _p2_repl[_fk2][0].encode() + _fm.group(2))
                        else:
                            res.extend(raw_b[i2:i2 + _fm.end()])
                        i2 += _fm.end(); continue
                    if raw_b[i2:i2+1] == b'(':
                        _j2, _d2 = i2 + 1, 1
                        while _j2 < len(raw_b) and _d2 > 0:
                            if raw_b[_j2] == 92:   _j2 += 2
                            elif raw_b[_j2] == 40:  _d2 += 1; _j2 += 1
                            elif raw_b[_j2] == 41:  _d2 -= 1; _j2 += 1
                            else:                    _j2 += 1
                        _fk2 = _cf2[0]
                        if _fk2 and _fk2 in _p2_repl:
                            _nk, _nu2g, _og2u = _p2_repl[_fk2]
                            _rs2 = _pdf_unescape(raw_b[i2+1:_j2-1])
                            _bw2 = max((len(_kk) for _kk in _og2u), default=1)
                            _dec2, _ki2 = [], 0
                            while _ki2 < len(_rs2):
                                _hit2 = False
                                for _w2 in range(_bw2, 0, -1):
                                    if _rs2[_ki2:_ki2+_w2] in _og2u:
                                        _dec2.append(_og2u[_rs2[_ki2:_ki2+_w2]])
                                        _ki2 += _w2; _hit2 = True; break
                                if not _hit2: _ki2 += 1
                            _conv2 = fn(''.join(_dec2))
                            _nb = bytearray()
                            for _ch2 in _conv2:
                                if not _ch2: continue
                                _code = _nu2g.get(_ch2)
                                if _code is None:
                                    _code = _nu2g.get(_FB2.get(_ch2, '?'))
                                if _code is None:
                                    _code = _nu2g.get(' ') or b'\x20'
                                _nb.extend(_code)
                            res.extend(b'(' + _pdf_escape(bytes(_nb)) + b')')
                            _n2[0] += 1; i2 = _j2; continue
                        res.extend(raw_b[i2:_j2]); i2 = _j2; continue
                    res.append(raw_b[i2]); i2 += 1
                return bytes(res), _n2[0]

            try:
                _p2_co2 = _p2_page.get('/Contents')
                if isinstance(_p2_co2, _pikepdf.Array):
                    for _s in _p2_co2:
                        try:
                            _nr, _nc = _p2_rewrite(_s.read_bytes())
                            if _nc > 0:
                                _s.write(_nr)
                                _p2_total += _nc
                        except Exception:
                            pass
                elif _p2_co2 is not None:
                    _nr, _nc = _p2_rewrite(_p2_co2.read_bytes())
                    if _nc > 0:
                        _p2_co2.write(_nr)
                        _p2_total += _nc
            except Exception as _e:
                log.warning('PDF phase-2 rewrite error: %s', _e)

        if _p2_total > 0:
            log.info('PDF phase-2: substituted font(s) and converted %d string(s)', _p2_total)
            _p2_out = BytesIO()
            _p2_src.save(_p2_out)
            return _p2_out.getvalue(), _p2_total
        log.debug('PDF phase-2: no substitutions needed or substitution produced 0 conversions')

    except Exception as _p2_err:
        import traceback
        log.warning('PDF phase-2 skipped: %s\n%s', _p2_err, traceback.format_exc())

    # ── Phase 3 & 4: Raw legacy-encoding stream patching ───────────────────────────────────────────
    # Many old Uzbek/Russian PDFs store Cyrillic text directly as cp1251 or
    # cp866 bytes in parenthesis strings, with no ToUnicode CMap.
    # We patch the bytes in-place so the entire PDF structure is untouched:
    # images, fonts, colours, layout and metadata all survive unchanged.
    _FALLBACK = {
        '\u02BB': "'", '\u02BC': "'",
        '\u2018': "'", '\u2019': "'",
        '\u201C': '"', '\u201D': '"',
    }

    def _safe_encode(text: str, enc: str) -> bytes:
        buf = bytearray()
        for ch in text:
            try:
                buf.extend(ch.encode(enc))
            except (UnicodeEncodeError, LookupError):
                fb = _FALLBACK.get(ch, '?')
                try:
                    buf.extend(fb.encode(enc))
                except Exception:
                    buf.extend(b'?')
        return bytes(buf)

    def _make_raw_conv(enc: str):
        """Return a stream-conversion function for the given legacy encoding."""
        def _conv(raw: bytes):
            result = bytearray()
            i = 0
            n_conv = 0

            while i < len(raw):
                if raw[i:i+1] == b'(':
                    j, depth = i + 1, 1
                    while j < len(raw) and depth > 0:
                        if raw[j] == 92:
                            j += 2
                        elif raw[j] == 40:
                            depth += 1; j += 1
                        elif raw[j] == 41:
                            depth -= 1; j += 1
                        else:
                            j += 1
                    raw_str = _pdf_unescape(raw[i+1:j-1])
                    if any(b >= 0x80 for b in raw_str):
                        try:
                            text = raw_str.decode(enc)
                            converted = fn(text)
                            if converted != text:
                                new_bytes = _safe_encode(converted, enc)
                                result.extend(b'(' + _pdf_escape(new_bytes) + b')')
                                n_conv += 1
                                i = j
                                continue
                        except (UnicodeDecodeError, LookupError):
                            pass
                    result.extend(raw[i:j])
                    i = j
                    continue

                if raw[i:i+1] == b'<' and i + 1 < len(raw) and raw[i+1:i+2] != b'<':
                    end = raw.find(b'>', i + 1)
                    if end != -1:
                        h = raw[i+1:end]
                        if (re.fullmatch(rb'[0-9A-Fa-f]+', h)
                                and len(h) % 2 == 0):
                            try:
                                raw_bytes = bytes.fromhex(h.decode())
                                if any(b >= 0x80 for b in raw_bytes):
                                    text = raw_bytes.decode(enc)
                                    converted = fn(text)
                                    if converted != text:
                                        new_bytes = _safe_encode(converted, enc)
                                        result.extend(
                                            b'<' + new_bytes.hex().upper().encode() + b'>'
                                        )
                                        n_conv += 1
                                        i = end + 1
                                        continue
                            except Exception:
                                pass
                        result.extend(raw[i:end+1])
                        i = end + 1
                        continue

                result.append(raw[i])
                i += 1

            return bytes(result), n_conv
        return _conv

    for enc in ('cp1251', 'cp866'):
        result_data, n = _apply_to_streams(data, _make_raw_conv(enc))
        if n > 0:
            log.info('PDF phase-3/4 (%s): converted %d raw string(s)', enc, n)
            return result_data, n
        log.debug('PDF phase-3/4 (%s): no high-byte Cyrillic strings found', enc)

    # Phase 5: UTF-16-BE paren strings — Cyrillic U+0410-U+04FF stored as big-endian
    # pairs (e.g. \x04\x10 for U+0410 = Cyrillic A).  Both bytes may be < 0x80 so
    # Phase 3/4's high-byte guard skips them entirely.
    def _conv_utf16be_paren(raw: bytes):
        result = bytearray()
        i = 0
        n_conv = 0
        while i < len(raw):
            if raw[i:i+1] == b'(':
                j = i + 1
                depth = 1
                while j < len(raw) and depth > 0:
                    if raw[j] == 92:   
                        j += 2
                    elif raw[j] == 40:  
                        depth += 1
                        j += 1
                    elif raw[j] == 41:  
                        depth -= 1
                        j += 1
                    else:
                        j += 1
                inner = _pdf_unescape(raw[i + 1:j - 1])
                if len(inner) >= 2 and len(inner) % 2 == 0:
                    try:
                        text = inner.decode('utf-16-be')
                        if any('Ѐ' <= c <= 'ӿ' for c in text):
                            converted = fn(text)
                            if converted != text:
                                nb = converted.encode('utf-16-be')
                                result.extend(b'(' + _pdf_escape(nb) + b')')
                                n_conv += 1
                                i = j
                                continue
                    except Exception:
                        pass
                result.extend(raw[i:j])
                i = j
                continue
            result.append(raw[i])
            i += 1
        return bytes(result), n_conv

    result_data5, n5 = _apply_to_streams(data, _conv_utf16be_paren)
    if n5 > 0:
        log.info('PDF phase-5 (UTF-16-BE paren): converted %d string(s)', n5)
        return result_data5, n5
    log.debug('PDF phase-5: no UTF-16-BE Cyrillic paren strings found')

    log.warning('PDF conversion: all phases returned 0 for mode=%s — '
                'PDF may be scanned, use custom encoding, or have no Cyrillic text', mode)
    return data, 0


@router.post("/tools/convert-file")
@limiter.limit("20/minute")
async def tools_convert_file(
    request: Request,
    file: UploadFile = File(...),
    mode: str = Form("k2l"),
):
    if mode not in ("k2l", "l2k"):
        raise HTTPException(400, detail="Noto'g'ri rejim.")

    data = await file.read()
    if len(data) > _MAX_CONV_SIZE:
        raise HTTPException(400, detail="Fayl hajmi 15 MB dan oshmasligi kerak.")

    fname = file.filename or "file"
    if "." in fname:
        base = fname.rsplit(".", 1)[0]
        ext = fname.rsplit(".", 1)[1].lower()
    else:
        base, ext = fname, ""

    if ext == "txt":
        result = await run_in_threadpool(_do_convert_txt, data, mode)
        media_type = "text/plain; charset=utf-8"
        out_name = base + "_converted.txt"
    elif ext == "docx":
        result = await run_in_threadpool(_do_convert_docx, data, mode)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        out_name = base + "_converted.docx"
    elif ext == "pdf":
        result, n_conv = await run_in_threadpool(_do_convert_pdf, data, mode)
        if n_conv == 0:
            opposite = "l2k" if mode == "k2l" else "k2l"
            result2, n_conv2 = await run_in_threadpool(_do_convert_pdf, data, opposite)
            if n_conv2 > 0:
                log.info(
                    "PDF auto-mode: user selected %s but PDF needed %s — retried successfully",
                    mode, opposite,
                )
                result, n_conv = result2, n_conv2
            else:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "PDF skanerlangan yoki qo'llab-quvvatlanmaydigan formatda. "
                        "Iltimos, matnli (text-based) PDF yuboring yoki "
                        "avval DOCX/TXT formatiga o'tkazib konvertatsiya qiling."
                    ),
                )
        media_type = "application/pdf"
        out_name = base + "_converted.pdf"
    else:
        raise HTTPException(
            400,
            detail="Qo'llab-quvvatlanmaydigan fayl formati. Faqat TXT, DOCX yoki PDF yuklang.",
        )

    return Response(
        content=result,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{out_name}"'},
    )


def _find_libreoffice():
    import shutil, os
    for c in [
        'libreoffice', 'soffice',
        r'C:\Program Files\LibreOffice\program\soffice.exe',
        r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
        '/usr/bin/libreoffice', '/usr/bin/soffice',
        '/usr/local/bin/libreoffice',
    ]:
        if shutil.which(c) or os.path.isfile(c):
            return c
    return None


_WIN_BUILTIN_FONTS = {
    'arial', 'arial black', 'arial narrow',
    'calibri', 'calibri light',
    'cambria', 'cambria math',
    'candara', 'consolas', 'constantia', 'corbel',
    'comic sans ms', 'courier new', 'courier',
    'ebrima', 'franklin gothic medium',
    'gabriola', 'gadugi', 'georgia',
    'impact', 'lucida console', 'lucida sans unicode',
    'malgun gothic', 'microsoft sans serif', 'microsoft yahei',
    'ms gothic', 'ms pgothic', 'ms ui gothic',
    'palatino linotype', 'segoe print', 'segoe script',
    'segoe ui', 'segoe ui light', 'segoe ui semibold', 'segoe ui symbol',
    'sylfaen', 'symbol',
    'tahoma', 'times new roman', 'times', 'trebuchet ms',
    'verdana', 'webdings', 'wingdings',
    'aptos', 'aptos display', 'bahnschrift',
}


def _available_fonts() -> set:
    """Return the set of font family names installed on the host (lower-cased).
    Works on Linux (fc-list) and Windows (scan %WINDIR%\\Fonts).  The result is
    cached for the lifetime of the process.  Empty set on failure (treated as
    'all fonts are present' so we never over-substitute)."""
    global _AVAILABLE_FONTS_CACHE
    try:
        return _AVAILABLE_FONTS_CACHE  # type: ignore[name-defined]
    except NameError:
        pass

    fonts: set = set()

    try:
        import subprocess
        out = subprocess.run(
            ['fc-list', ':', 'family'],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0:
            for line in out.stdout.splitlines():
                for fam in line.split(','):
                    fonts.add(fam.strip().lower())
    except Exception as _e:
        log.debug("fc-list unavailable: %s", _e)

    import sys as _sys, os as _os
    if _sys.platform == 'win32':
        try:
            from fontTools.ttLib import TTFont  # type: ignore
            _HAVE_FT = True
        except Exception:
            _HAVE_FT = False

        win_dirs = []
        if _os.environ.get('WINDIR'):
            win_dirs.append(_os.path.join(_os.environ['WINDIR'], 'Fonts'))
        if _os.environ.get('LOCALAPPDATA'):
            win_dirs.append(_os.path.join(
                _os.environ['LOCALAPPDATA'], 'Microsoft', 'Windows', 'Fonts'))

        for d in win_dirs:
            if not _os.path.isdir(d):
                continue
            for fn in _os.listdir(d):
                lower = fn.lower()
                if not lower.endswith(('.ttf', '.otf', '.ttc', '.fon')):
                    continue
                if _HAVE_FT:
                    try:
                        tt = TTFont(_os.path.join(d, fn), lazy=True,
                                    fontNumber=0)
                        for rec in tt['name'].names:  # type: ignore[attr-defined]
                            if rec.nameID in (1, 16): 
                                try:
                                    fonts.add(str(rec).strip().lower())
                                except Exception:
                                    pass
                        tt.close()
                        continue
                    except Exception:
                        pass
                stem = _os.path.splitext(fn)[0]
                stem = stem.replace('-', '').replace('_', '')
                fonts.add(stem.lower())

        if not fonts:
            fonts |= _WIN_BUILTIN_FONTS

    globals()['_AVAILABLE_FONTS_CACHE'] = fonts
    return fonts


def _flatten_letter_spacing(data: bytes) -> bytes:
    """Zero-out positive *character* spacing inside a DOCX so the resulting
    PDF doesn't show ugly inter-letter gaps.

    Word's "Format -> Font -> Advanced -> Spacing: Expanded by N pt" setting
    is stored as `<w:spacing w:val="N"/>` inside a run-properties block
    (`<w:rPr>`).  Positive `N` values appear faint on screen but render as
    wide letter spacing in any PDF export (whether via Word, docx2pdf, or
    LibreOffice).  This routine flips all such positive values to 0, leaving
    paragraph-level spacing (`<w:spacing w:before=".." w:after=".." w:line="..">`)
    completely untouched.

    Returns the original bytes on any unexpected failure so the conversion
    pipeline degrades gracefully.
    """
    import zipfile, io, re as _re

    _SPACING_RE = _re.compile(rb'<w:spacing(\s[^/>]*)/>')
    _VAL_RE     = _re.compile(rb'\bw:val="(-?\d+)"')
    _PARA_KEYS  = (b'w:before', b'w:after', b'w:line', b'w:beforeAutospacing',
                   b'w:afterAutospacing', b'w:beforeLines', b'w:afterLines',
                   b'w:lineRule')

    def _repl(m: '_re.Match[bytes]') -> bytes:
        attrs = m.group(1)
        if any(k in attrs for k in _PARA_KEYS):
            return m.group(0)
        mv = _VAL_RE.search(attrs)
        if not mv:
            return m.group(0)
        try:
            val = int(mv.group(1))
        except ValueError:
            return m.group(0)
        if val <= 0:
            return m.group(0)
        return b'<w:spacing w:val="0"/>'

    try:
        buf = io.BytesIO(data)
        out = io.BytesIO()
        n_changed = 0
        with zipfile.ZipFile(buf, 'r') as zin, \
             zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                raw = zin.read(item.filename)
                if (item.filename.startswith('word/')
                        and item.filename.endswith('.xml')):
                    new = _SPACING_RE.sub(_repl, raw)
                    if new != raw:
                        n_changed += 1
                    raw = new
                zout.writestr(item, raw)
        if n_changed:
            log.info("letter-spacing flatten: rewrote %d XML part(s) in DOCX",
                     n_changed)
        return out.getvalue()
    except Exception as _e:
        log.warning("letter-spacing flatten failed: %s — using original bytes",
                    _e)
        return data


def _substitute_fonts_for_lo(data: bytes) -> bytes:
    """Replace Windows/Mac-only fonts inside a DOCX with metric-compatible
    equivalents so LibreOffice can render the document with the SAME line
    widths, line wrapping, and overall layout as MS Word.

    Critical pairings (metric-compatible, glyph widths identical):
      - Calibri / Calibri Light  → Carlito    (Google's Calibri metric clone)
      - Cambria / Cambria Math   → Caladea    (Google's Cambria metric clone)
      - Arial                     → Liberation Sans   (Arial metric clone)
      - Times New Roman           → Liberation Serif  (Times metric clone)
      - Courier New / Consolas    → Liberation Mono   (Courier metric clone)

    Using non-metric-compatible fallbacks (e.g. Calibri → Liberation Sans)
    causes character widths to differ — LibreOffice tries to preserve word
    boundaries but ends up inserting visible inter-letter gaps in the PDF.
    This was the root cause of the 'X a l q a r o' spacing bug.
    """
    import zipfile, io, re as _re

    _avail = _available_fonts()

    def _pick(*candidates: str) -> str:
        """Return the first candidate font that exists on the system.
        Falls back to the last candidate if none are installed so the
        substitution is still applied and LibreOffice's own fallback chain
        takes over."""
        for c in candidates:
            if c.lower() in _avail:
                return c
        return candidates[-1]

    _CAL_SANS  = _pick('Carlito', 'Liberation Sans')          # Calibri-equivalent
    _CAM_SERIF = _pick('Caladea', 'Liberation Serif')         # Cambria-equivalent
    _ARI_SANS  = _pick('Liberation Sans', 'DejaVu Sans')      # Arial-equivalent
    _TNR_SERIF = _pick('Liberation Serif', 'DejaVu Serif')    # Times-equivalent
    _MONO      = _pick('Liberation Mono', 'DejaVu Sans Mono') # Courier-equivalent
    _SANS_NAR  = _pick('Liberation Sans Narrow', _ARI_SANS)

    _CANDIDATE_SUBS = {
        r'Calibri Light':       _CAL_SANS,
        r'Calibri':             _CAL_SANS,
        r'Cambria Math':        _CAM_SERIF,
        r'Cambria':             _CAM_SERIF,
        r'Aptos Display':       _CAL_SANS,
        r'Aptos':               _CAL_SANS,
        r'Arial Narrow':        _SANS_NAR,
        r'Arial Black':         _ARI_SANS,
        r'Arial':               _ARI_SANS,
        r'Times New Roman':     _TNR_SERIF,
        r'Times':               _TNR_SERIF,
        r'Courier New':         _MONO,
        r'Courier':             _MONO,
        r'Consolas':            _MONO,
        r'Lucida Console':      _MONO,
        r'Lucida Sans Unicode': _ARI_SANS,
        r'Lucida Sans':         _ARI_SANS,
        r'Century Gothic':      _ARI_SANS,
        r'Comic Sans MS':       _ARI_SANS,
        r'Franklin Gothic Medium': _ARI_SANS,
        r'Franklin Gothic':     _ARI_SANS,
        r'Garamond':            _TNR_SERIF,
        r'Georgia':             _TNR_SERIF,
        r'Helvetica Neue':      _ARI_SANS,
        r'Helvetica':           _ARI_SANS,
        r'Palatino Linotype':   _TNR_SERIF,
        r'Palatino':            _TNR_SERIF,
        r'Segoe UI Light':      _CAL_SANS,
        r'Segoe UI Semibold':   _CAL_SANS,
        r'Segoe UI':            _CAL_SANS,
        r'Tahoma':              _ARI_SANS,
        r'Trebuchet MS':        _ARI_SANS,
        r'Verdana':             _ARI_SANS,
        r'MS Sans Serif':       _ARI_SANS,
        r'MS Serif':            _TNR_SERIF,
        r'MS Reference Sans Serif': _ARI_SANS,
        r'Book Antiqua':        _TNR_SERIF,
        r'Bookman Old Style':   _TNR_SERIF,
        r'Symbol':              _TNR_SERIF,
        r'Wingdings':           _TNR_SERIF,
        r'Webdings':            _TNR_SERIF,
    }

    if _avail:  
        _SUBS = {
            k: v for k, v in _CANDIDATE_SUBS.items()
            if k.lower() not in _avail and v.lower() in _avail
        }
    else:
        _SUBS = dict(_CANDIDATE_SUBS)

    if not _SUBS:
        log.info("font-subst: all source fonts present on host, skipping")
        return data

    _sorted_keys = sorted(_SUBS.keys(), key=len, reverse=True)
    _pattern = _re.compile(
        r'(?<![A-Za-z])(' + '|'.join(_re.escape(k) for k in _sorted_keys) + r')(?![A-Za-z])',
        _re.IGNORECASE,
    )

    def _apply_subs(xml_bytes: bytes) -> bytes:
        try:
            text = xml_bytes.decode('utf-8')
        except Exception:
            return xml_bytes
        def _repl(m):
            orig = m.group(1)
            for k, v in _SUBS.items():
                if orig.lower() == k.lower():
                    return v
            return orig
        return _pattern.sub(_repl, text).encode('utf-8')

    buf = io.BytesIO(data)
    out = io.BytesIO()
    try:
        with zipfile.ZipFile(buf, 'r') as zin, zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                raw = zin.read(item.filename)
                if item.filename.startswith('word/') and item.filename.endswith('.xml'):
                    raw = _apply_subs(raw)
                zout.writestr(item, raw)
        return out.getvalue()
    except Exception:
        return data  


def _libreoffice_convert(data: bytes, src_ext: str, tgt_ext: str) -> bytes:
    import subprocess, tempfile, os

    lo = _find_libreoffice()
    if not lo:
        raise ValueError(
            "LibreOffice topilmadi. Ushbu konvertatsiya uchun serverda "
            "LibreOffice o'rnatilgan bo'lishi kerak."
        )
    if src_ext == 'docx':
        data = _substitute_fonts_for_lo(data)

    convert_to_arg = 'pdf' if tgt_ext == 'pdf' else tgt_ext

    with tempfile.TemporaryDirectory() as tmp:
        src_path = os.path.join(tmp, f'input.{src_ext}')
        with open(src_path, 'wb') as f:
            f.write(data)

        profile_dir = os.path.join(tmp, 'lo_profile')
        user_install = f'-env:UserInstallation=file://{profile_dir}'

        lo_home  = os.path.join(tmp, 'home')
        lo_cache = os.path.join(lo_home, '.cache')
        lo_cfg   = os.path.join(lo_home, '.config')
        lo_data  = os.path.join(lo_home, '.local', 'share')
        lo_run   = os.path.join(lo_home, 'run')
        for d in (lo_cache, lo_cfg, lo_data, lo_run):
            os.makedirs(d, exist_ok=True)
        try:
            os.chmod(lo_run, 0o700)
        except OSError:
            pass

        env = os.environ.copy()
        env['HOME']            = lo_home
        env['XDG_CACHE_HOME']  = lo_cache
        env['XDG_CONFIG_HOME'] = lo_cfg
        env['XDG_DATA_HOME']   = lo_data
        env['XDG_RUNTIME_DIR'] = lo_run
        env['TMPDIR']          = tmp
        env['FONTCONFIG_PATH'] = '/etc/fonts'
        env.setdefault('LANG',   'C.UTF-8')
        env.setdefault('LC_ALL', 'C.UTF-8')

        cmd = [
            lo, user_install,
            '--headless', '--norestore', '--nologo', '--nolockcheck',
            '--convert-to', convert_to_arg,
            '--outdir', tmp,
            src_path,
        ]

        try:
            proc = subprocess.run(
                cmd, timeout=180, check=False, capture_output=True, env=env,
            )
        except subprocess.TimeoutExpired:
            raise ValueError(
                "Konvertatsiya 180 soniyadan ortiq vaqt oldi. "
                "Faylni kichikroq qiling yoki keyinroq urinib ko'ring."
            )

        out_path = os.path.join(tmp, f'input.{tgt_ext}')
        if proc.returncode != 0 or not os.path.exists(out_path):
            stderr = proc.stderr.decode('utf-8', errors='replace')[:500]
            stdout = proc.stdout.decode('utf-8', errors='replace')[:500]
            log.error(
                "LibreOffice convert failed (%s→%s, rc=%d): stderr=%s stdout=%s",
                src_ext, tgt_ext, proc.returncode, stderr, stdout,
            )
            raise ValueError(
                "Konvertatsiya muvaffaqiyatsiz yakunlandi. "
                "Fayl format xato yoki buzilgan bo'lishi mumkin."
            )
        with open(out_path, 'rb') as f:
            return f.read()


def _pdf_to_docx_smart(data: bytes) -> bytes:
    """Convert PDF to DOCX using PyMuPDF with TEXT_INHIBIT_SPACES for clean text extraction.
    Handles Word-generated PDFs with TJ kerning arrays that cause spurious spaces."""
    try:
        try:
            import fitz
        except ImportError:
            import pymupdf as fitz  # type: ignore[no-redef]
        from docx import Document as _DocxDoc
        from docx.shared import Pt as _Pt, RGBColor as _RGB, Cm as _Cm
        from docx.enum.text import WD_ALIGN_PARAGRAPH as _WDA
        import os

        src = fitz.open(stream=data, filetype='pdf')
        doc = _DocxDoc()

        for section in doc.sections:
            section.top_margin    = _Cm(2.0)
            section.bottom_margin = _Cm(2.0)
            section.left_margin   = _Cm(2.5)
            section.right_margin  = _Cm(2.5)

        for p in doc.paragraphs:
            p._element.getparent().remove(p._element)

        import sys as _sys
        if _sys.platform == 'win32':
            _FC_FONT = 'Arial'
        elif os.path.exists('/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'):
            _FC_FONT = 'Liberation Sans'
        elif os.path.exists('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
            _FC_FONT = 'DejaVu Sans'
        else:
            _FC_FONT = 'Arial'

        _FONT_SUBS: dict = {} if _sys.platform == 'win32' else {
            'arial':           'Liberation Sans',
            'arial narrow':    'Liberation Sans Narrow',
            'calibri':         'Liberation Sans',
            'calibri light':   'Liberation Sans',
            'cambria':         'Liberation Serif',
            'cambria math':    'Liberation Serif',
            'century gothic':  'Liberation Sans',
            'comic sans ms':   'Liberation Sans',
            'consolas':        'Liberation Mono',
            'courier new':     'Liberation Mono',
            'courier':         'Liberation Mono',
            'georgia':         'Liberation Serif',
            'helvetica':       'Liberation Sans',
            'tahoma':          'Liberation Sans',
            'times new roman': 'Liberation Serif',
            'times':           'Liberation Serif',
            'trebuchet ms':    'Liberation Sans',
            'verdana':         'Liberation Sans',
        }

        for page_num, page in enumerate(src):
            if page_num > 0:
                doc.add_page_break()

            flags = fitz.TEXT_INHIBIT_SPACES | fitz.TEXT_PRESERVE_WHITESPACE
            blocks = page.get_text('dict', flags=flags)['blocks']

            for block in blocks:
                if block.get('type') != 0:
                    continue

                lines = block.get('lines', [])
                if not lines:
                    continue

                page_w = page.rect.width
                block_x0 = block['bbox'][0]
                block_x1 = block['bbox'][2]
                block_cx = (block_x0 + block_x1) / 2
                align = _WDA.LEFT
                if abs(block_cx - page_w / 2) < page_w * 0.1:
                    align = _WDA.CENTER
                elif block_x1 > page_w * 0.8 and block_x0 > page_w * 0.5:
                    align = _WDA.RIGHT

                para = doc.add_paragraph()
                para.alignment = align

                for li, line in enumerate(lines):
                    if li > 0:
                        para.add_run('\n')

                    for span in line.get('spans', []):
                        text = span.get('text', '').rstrip('\n')
                        if not text:
                            continue

                        run = para.add_run(text)

                        fsize = span.get('size', 11)
                        run.font.size = _Pt(round(fsize, 1))

                        f = span.get('flags', 0)
                        is_bold   = bool(f & 16)
                        is_italic = bool(f & 2)
                        run.bold   = is_bold
                        run.italic = is_italic

                        font_raw = span.get('font', _FC_FONT)
                        font_name = font_raw.split(',')[0].split('-')[0].replace('MT', '').strip()
                        font_name = font_name or _FC_FONT
                        font_name = _FONT_SUBS.get(font_name.lower(), font_name) or _FC_FONT
                        run.font.name = font_name

                        try:
                            from docx.oxml.ns import qn as _qn
                            from lxml import etree as _etree
                            _rPr = run._r.get_or_add_rPr()

                            _rFonts = _rPr.find(_qn('w:rFonts'))
                            if _rFonts is None:
                                _rFonts = _etree.SubElement(_rPr, _qn('w:rFonts'))
                            _rFonts.set(_qn('w:ascii'),    font_name)
                            _rFonts.set(_qn('w:hAnsi'),    font_name)
                            _rFonts.set(_qn('w:cs'),       font_name)
                            _rFonts.set(_qn('w:eastAsia'), font_name)

                            def _ensure_cs_elem(tag, present):
                                el = _rPr.find(_qn(tag))
                                if present and el is None:
                                    _etree.SubElement(_rPr, _qn(tag))
                                elif not present and el is not None:
                                    _rPr.remove(el)
                            _ensure_cs_elem('w:bCs', is_bold)
                            _ensure_cs_elem('w:iCs', is_italic)

                            sz_half = str(round(fsize * 2))
                            _szCs = _rPr.find(_qn('w:szCs'))
                            if _szCs is None:
                                _szCs = _etree.SubElement(_rPr, _qn('w:szCs'))
                            _szCs.set(_qn('w:val'), sz_half)
                        except Exception:
                            pass

                        color_int = span.get('color', 0)
                        if color_int:
                            r = (color_int >> 16) & 0xFF
                            g = (color_int >> 8)  & 0xFF
                            b =  color_int        & 0xFF
                            run.font.color.rgb = _RGB(r, g, b)

        out = BytesIO()
        doc.save(out)
        return out.getvalue()

    except Exception as _fitz_err:
        import traceback as _tb
        _msg = _tb.format_exc()
        log.error("_pdf_to_docx_smart FAILED: %s\n%s", _fitz_err, _msg)
        print(f"\n[PDF->DOCX ERROR] {_fitz_err}\n{_msg}", flush=True)
        try:
            from pdf2docx import Converter as _Cv
            import tempfile, os
            with tempfile.TemporaryDirectory() as tmp:
                sp = os.path.join(tmp, 'in.pdf')
                dp = os.path.join(tmp, 'out.docx')
                with open(sp, 'wb') as f:
                    f.write(data)
                cv = _Cv(sp)
                cv.convert(dp)
                cv.close()
                with open(dp, 'rb') as f:
                    return f.read()
        except ImportError:
            raise ValueError(
                "pymupdf yoki pdf2docx kutubxonasi o'rnatilmagan. "
                "pip install pymupdf pdf2docx"
            )


def _do_format_convert(data: bytes, src_ext: str, tgt_ext: str) -> bytes:
    """Convert file bytes from src_ext format to tgt_ext format."""
    src = src_ext.lower().lstrip('.')
    tgt = tgt_ext.lower().lstrip('.')
    if src == 'jpeg':
        src = 'jpg'
    if tgt == 'jpeg':
        tgt = 'jpg'
    if src == tgt:
        return data

    if src in _IMG_EXTS and tgt in _IMG_EXTS:
        from PIL import Image
        img = Image.open(BytesIO(data))
        if img.mode in ('RGBA', 'LA', 'P') and tgt in ('jpg', 'bmp'):
            img = img.convert('RGB')
        out = BytesIO()
        fmt = {'jpg': 'JPEG', 'png': 'PNG', 'webp': 'WEBP', 'bmp': 'BMP'}[tgt]
        img.save(out, format=fmt, quality=92)
        return out.getvalue()

    if src in _IMG_EXTS and tgt == 'pdf':
        from PIL import Image
        img = Image.open(BytesIO(data))
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        out = BytesIO()
        img.save(out, format='PDF', resolution=150)
        return out.getvalue()

    if src == 'pdf' and tgt == 'txt':
        import pypdf
        reader = pypdf.PdfReader(BytesIO(data))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        if not pages:
            raise ValueError("PDF matn qatlamsiz (skanerlangan). Matnli PDF yuboring.")
        return '\n\n'.join(pages).encode('utf-8')

    if src == 'pdf' and tgt == 'docx':
        return _pdf_to_docx_smart(data)

    if src == 'docx' and tgt == 'txt':
        from docx import Document
        doc = Document(BytesIO(data))
        text = '\n'.join(p.text for p in doc.paragraphs)
        return text.encode('utf-8')

    if src == 'txt' and tgt == 'docx':
        from docx import Document
        text = data.decode('utf-8', errors='replace')
        doc = Document()
        for line in text.splitlines():
            doc.add_paragraph(line)
        out = BytesIO()
        doc.save(out)
        return out.getvalue()

    if src == 'txt' and tgt == 'pdf':
        import os
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        text = data.decode('utf-8', errors='replace')
        out = BytesIO()
        doc = SimpleDocTemplate(out, pagesize=A4,
                                leftMargin=2*cm, rightMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()

        for fp in [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            'C:/Windows/Fonts/arial.ttf',
            '/Library/Fonts/Arial.ttf',
        ]:
            if os.path.exists(fp):
                pdfmetrics.registerFont(TTFont('_TxtPdfFont', fp))
                styles['Normal'].fontName = '_TxtPdfFont'
                break

        story = []
        for line in text.splitlines() or ['']:
            if line.strip():
                story.append(Paragraph(
                    line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'),
                    styles['Normal'],
                ))
            else:
                story.append(Spacer(1, 12))
        doc.build(story)
        return out.getvalue()

    if src == 'xlsx' and tgt == 'csv':
        from openpyxl import load_workbook
        import csv, io as _io
        wb = load_workbook(BytesIO(data), data_only=True)
        ws = wb.active
        buf = _io.StringIO()
        writer = csv.writer(buf)
        for row in ws.iter_rows(values_only=True):
            writer.writerow(['' if v is None else v for v in row])
        return buf.getvalue().encode('utf-8-sig')

    if src == 'csv' and tgt == 'xlsx':
        from openpyxl import Workbook
        import csv, io as _io
        text = data.decode('utf-8-sig', errors='replace')
        wb = Workbook()
        ws = wb.active
        for row in csv.reader(_io.StringIO(text)):
            ws.append(row)
        out = BytesIO()
        wb.save(out)
        return out.getvalue()

    if src == 'docx' and tgt == 'pdf':
        import sys as _sys, tempfile as _tf, os as _os
        data = _flatten_letter_spacing(data)
        if _sys.platform == 'win32':
            try:
                import docx2pdf as _d2p
                with _tf.TemporaryDirectory() as _tmp:
                    _sp = _os.path.join(_tmp, 'input.docx')
                    with open(_sp, 'wb') as f:
                        f.write(data)
                    _d2p.convert(_sp)
                    _dp = _sp.replace('.docx', '.pdf')
                    if _os.path.exists(_dp):
                        log.info("DOCX-PDF: MS Word (docx2pdf) used successfully")
                        with open(_dp, 'rb') as f:
                            return f.read()
                    log.warning("DOCX-PDF: docx2pdf ran but PDF not found at %s, trying LibreOffice", _dp)
            except ImportError:
                log.info("DOCX-PDF: docx2pdf not installed, trying LibreOffice")
            except Exception as _e:
                log.warning("DOCX-PDF: docx2pdf failed (%s), trying LibreOffice", _e)
        log.info("DOCX-PDF: using LibreOffice")
        return _libreoffice_convert(data, src, tgt)

    lo_pairs = {
        ('pptx', 'pdf'),
        ('odt', 'pdf'), ('odt', 'docx'),
        ('ods', 'xlsx'), ('ods', 'csv'),
        ('odp', 'pdf'),
    }
    if (src, tgt) in lo_pairs:
        return _libreoffice_convert(data, src, tgt)

    raise ValueError(
        f"'{src.upper()}' dan '{tgt.upper()}' ga konvertatsiya qo'llab-quvvatlanmaydi."
    )


@router.get("/tools/file-converter", response_class=HTMLResponse)
async def tools_file_converter_page(request: Request):
    context = await get_template_context(request)
    return templates.TemplateResponse("teacher/tools/file_converter.html", context)


@router.post("/tools/file-converter")
@limiter.limit("15/minute")
async def tools_file_converter(
    request: Request,
    file: UploadFile = File(...),
    target: str = Form(...),
):
    data = await file.read()
    if len(data) > _MAX_FC_SIZE:
        raise HTTPException(400, detail="Fayl hajmi 50 MB dan oshmasligi kerak.")

    fname = file.filename or "file"
    src_ext = fname.rsplit('.', 1)[-1].lower() if '.' in fname else ''
    tgt_ext = target.lower().lstrip('.')
    base = fname.rsplit('.', 1)[0] if '.' in fname else fname

    if src_ext not in _FC_MAP:
        raise HTTPException(400, detail=f"'{src_ext.upper()}' fayl formati qo'llab-quvvatlanmaydi.")
    if tgt_ext not in _FC_MAP.get(src_ext, []):
        raise HTTPException(400, detail=f"'{src_ext.upper()}' dan '{tgt_ext.upper()}' ga konvertatsiya mumkin emas.")

    try:
        result = await run_in_threadpool(_do_format_convert, data, src_ext, tgt_ext)
    except ValueError as e:
        raise HTTPException(422, detail=str(e))
    except Exception as e:
        log.exception("File converter error: %s -> %s", src_ext, tgt_ext)
        raise HTTPException(500, detail=f"Konvertatsiya xatosi: {e}")

    out_ext = 'jpg' if tgt_ext == 'jpeg' else tgt_ext
    media_type = _FC_MIME.get(tgt_ext, 'application/octet-stream')
    out_name = f"{base}_converted.{out_ext}"

    return StreamingResponse(
        BytesIO(result),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{out_name}"',
            "Content-Length": str(len(result)),
        },
    )
