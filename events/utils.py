import re


def normalize_image_url(url: str) -> str:
    """
    Convert a public Google Drive share link into a directly-embeddable
    image URL. Falls back to returning the original URL unchanged for
    any URL that isn't a recognizable Drive share link (e.g. normal
    public image URLs).
    """
    if not url:
        return url

    patterns = [
        r"drive\.google\.com/file/d/([a-zA-Z0-9_-]+)",
        r"drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)",
        r"drive\.google\.com/uc\?id=([a-zA-Z0-9_-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            file_id = match.group(1)
            return f"https://drive.google.com/uc?export=view&id={file_id}"

    return url
