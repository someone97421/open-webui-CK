from __future__ import annotations

import io
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from PIL import Image, ImageOps

from open_webui.env import DATA_DIR
from open_webui.models.config import Config

BRANDING_DIR = Path(DATA_DIR) / 'branding'
BRANDING_LOGO_PREFIX = '/api/v1/configs/interface/branding/logo/'
DEFAULT_LOGO_URL = '/static/favicon.png'
LOGO_MAX_BYTES = 10 * 1024 * 1024
LOGO_MAX_PIXELS = 25_000_000
LOGO_FILENAME_PATTERN = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.png')


def get_branding_logo_path(filename: str) -> Path | None:
    if not LOGO_FILENAME_PATTERN.fullmatch(filename):
        return None
    path = BRANDING_DIR / filename
    if path.is_symlink() or not path.is_file():
        return None
    return path


def validate_branding_logo_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ''
    if len(value) > 2048 or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError('Logo URL must be a valid URL of at most 2048 characters.')
    if value.startswith(BRANDING_LOGO_PREFIX):
        if get_branding_logo_path(value.removeprefix(BRANDING_LOGO_PREFIX)) is not None:
            return value
        raise ValueError('Uploaded logo does not exist.')
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() in {'http', 'https'} and parsed.hostname and '\\' not in value:
            parsed.port
            return value
    except ValueError:
        pass
    raise ValueError('Logo URL must use HTTP(S) or reference an uploaded logo.')


async def get_site_branding(default_name: str) -> dict[str, str]:
    values = await Config.get_many('ui.custom_name', 'ui.custom_logo_url')
    name = values.get('ui.custom_name')
    name = name.strip() if isinstance(name, str) else ''
    logo_url = values.get('ui.custom_logo_url')
    try:
        logo_url = validate_branding_logo_url(logo_url) if isinstance(logo_url, str) else ''
    except ValueError:
        logo_url = ''
    return {
        'name': name if name and len(name) <= 128 else default_name,
        'logo_url': logo_url or DEFAULT_LOGO_URL,
    }


def save_branding_logo(data: bytes) -> str:
    if not data or len(data) > LOGO_MAX_BYTES:
        raise ValueError('Logo must be a nonempty image of at most 10 MiB.')
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in {'PNG', 'JPEG', 'WEBP', 'GIF', 'ICO', 'BMP', 'TIFF', 'AVIF'}:
                raise ValueError('Unsupported logo image format.')
            if image.width * image.height > LOGO_MAX_PIXELS:
                raise ValueError('Logo image must not exceed 25 megapixels.')
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            image.seek(0)
            image = ImageOps.exif_transpose(image)
            image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            normalized = Image.new('RGBA', image.size)
            normalized.paste(image.convert('RGBA'))
            output = io.BytesIO()
            normalized.save(output, format='PNG')
    except (OSError, SyntaxError, Image.DecompressionBombError) as error:
        raise ValueError('Invalid logo image.') from error

    BRANDING_DIR.mkdir(parents=True, exist_ok=True)
    filename = f'{uuid4()}.png'
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=BRANDING_DIR, suffix='.tmp', delete=False) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(output.getvalue())
        os.replace(temporary_path, BRANDING_DIR / filename)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return f'{BRANDING_LOGO_PREFIX}{filename}'
