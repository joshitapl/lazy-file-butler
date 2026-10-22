"""Bounded local readers. Tesseract handles OCR; no model or network downloads."""
from pathlib import Path
import shutil
import sys
import subprocess
import zipfile
import xml.etree.ElementTree as ET

TEXT = {'.txt', '.md', '.csv', '.json', '.py', '.js', '.html', '.css', '.log', '.yaml', '.yml', '.ts', '.tsx', '.jsx', '.rst', '.tex'}
IMAGES = {'.png', '.jpg', '.jpeg', '.webp', '.tiff', '.tif', '.bmp'}
SUPPORTED = TEXT | IMAGES | {'.pdf', '.docx'}


def native_binary():
    p = Path(__file__).parent/'data'/'macos-ocr'
    return p if sys.platform == 'darwin' and p.is_file() else None


def prepare_native():
    """Compile a small bridge to the system Vision framework; never fetch a model."""
    if sys.platform != 'darwin' or native_binary() or not shutil.which('swiftc'):
        return
    base = Path(__file__).parent
    cache = base/'data'/'native-cache'
    cache.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(['swiftc', '-O', '-module-cache-path', str(cache),
                        str(base/'native'/'ocr.swift'), '-o', str(base/'data'/'macos-ocr')],
                       capture_output=True, timeout=90, check=True)
    except (OSError, subprocess.SubprocessError):
        pass  # Tesseract remains available; no installer is invoked.


def ocr_status():
    native = native_binary()
    return {'available': bool(native or shutil.which('tesseract')),
            'engine': 'macOS Vision' if native else 'Tesseract', 'language': 'English'}


def ocr_png(data):
    native = native_binary()
    native_text = ''
    if native:
        result = subprocess.run([str(native)], input=data, capture_output=True, timeout=40)
        if not result.returncode:
            native_text = result.stdout.decode('utf-8', errors='replace').strip()
            if len(native_text) >= 30:
                return native_text
    command = shutil.which('tesseract')
    if not command:
        if native_text:
            return native_text
        raise ValueError('Local OCR is unavailable. You can still sort this file by type.')
    result = subprocess.run([command, 'stdin', 'stdout', '-l', 'eng', '--psm', '3'],
                            input=data, capture_output=True, timeout=40)
    if result.returncode:
        if native_text:
            return native_text
        raise ValueError('OCR could not read this page. You can still sort this file manually.')
    text = result.stdout.decode('utf-8', errors='replace').strip()
    return max((text, native_text), key=lambda t: len(t))


def sample_pages(count):
    # Covers the front matter and later pages without reading an entire textbook.
    first = list(range(min(12, count)))
    return sorted(set(first + ([count//4, count//2, 3*count//4, count-1] if count else [])))


def render_page(page):
    import pymupdf
    scale = min(2.5, 2600 / max(page.rect.width, page.rect.height, 1))
    return page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes('png')


def extract(path, progress=None):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in TEXT:
        with path.open('rb') as stream:
            text = stream.read(16000).decode('utf-8', errors='replace').strip()
        return {'text': text[:12000], 'method': 'Text', 'pages': [], 'warning': None}
    if suffix == '.docx':
        with zipfile.ZipFile(path) as archive:
            info = archive.getinfo('word/document.xml')
            if info.file_size > 8*1024*1024:
                raise ValueError('The Word document is too large to extract safely.')
            node = ET.fromstring(archive.read(info))
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        text = '\n'.join(''.join(p.itertext()) for p in node.findall('.//w:p', ns))
        return {'text': text[:12000], 'method': 'Word text', 'pages': [], 'warning': None}
    if suffix not in IMAGES | {'.pdf'}:
        return {'text': '', 'method': 'File type', 'pages': [], 'warning': None}
    import pymupdf
    with pymupdf.open(path) as document:
        if document.needs_pass:
            raise ValueError('Password-protected PDF. Unlock a copy or sort by file type.')
        if suffix in IMAGES:
            if progress:
                progress('Reading image text with OCR')
            text = ocr_png(render_page(document[0]))
            return {'text': text[:12000], 'method': 'Image OCR', 'pages': [1],
                    'warning': 'OCR reads visible English text; it does not recognize image subjects.'}
        chunks, used = [], []
        for i in sample_pages(len(document)):
            text = document[i].get_text().strip()
            if text:
                chunks.append(f'[Page {i+1}]\n{text}')
                used.append(i+1)
            if sum(len(t) for t in chunks) >= 10000:
                break
        if sum(len(t) for t in chunks) >= 120:
            return {'text': '\n\n'.join(chunks)[:12000], 'method': 'PDF text', 'pages': used,
                    'warning': 'Sampled pages, not the full document.'}
        # No useful text layer: OCR a bounded sample, including later pages.
        ocr_pages = list(dict.fromkeys([i for i in [0, 1, 2, 3, 5, 8, len(document)//2, len(document)-1]
                                      if 0 <= i < len(document)]))
        for i in ocr_pages:
            if progress:
                progress(f'OCR: page {i+1} of {len(document)}')
            text = ocr_png(render_page(document[i]))
            if text:
                chunks.append(f'[Page {i+1}, OCR]\n{text}')
                used.append(i+1)
            if sum(len(t) for t in chunks) >= 8500:
                break
        return {'text': '\n\n'.join(chunks)[:12000], 'method': 'PDF OCR', 'pages': sorted(set(used)),
                'warning': 'OCR can misread words. Sampled up to 8 pages; inspect the extracted text.'}
