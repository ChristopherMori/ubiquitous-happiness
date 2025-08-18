import re
from slugify import slugify as _slugify

def slugify(title: str) -> str:
    s = _slugify(title or "", lowercase=True)
    s = re.sub(r'-{2,}', '-', s).strip('-')
    return s or "untitled"
