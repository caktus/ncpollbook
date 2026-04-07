"""
Download and extract NCSBE voter data files from S3.

Files are cached in SCRATCH_DIR and only re-downloaded if the ZIP is older
than MAX_CACHE_AGE (default: 7 days).
"""

import datetime
import zipfile
from pathlib import Path

import httpx

from apps.ncsbe.constants import (
    NCVHIS_TXT_FILENAME,
    NCVHIS_ZIP_URL,
    NCVOTER_TXT_FILENAME,
    NCVOTER_ZIP_URL,
)

MAX_CACHE_AGE = datetime.timedelta(days=7)


def is_fresh(path: Path, max_age: datetime.timedelta = MAX_CACHE_AGE) -> bool:
    """Return True if *path* exists and was modified within *max_age*."""
    if not path.exists():
        return False
    age = datetime.datetime.now() - datetime.datetime.fromtimestamp(path.stat().st_mtime)
    return age < max_age


def _download_file(url: str, dest: Path) -> None:
    """Stream-download a URL to a local file, showing a progress indicator."""
    with httpx.stream("GET", url, follow_redirects=True, timeout=600) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        downloaded = 0
        with dest.open("wb") as fh:
            for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                fh.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    print(f"\r  {dest.name}: {pct:.1f}%", end="", flush=True)
        print()  # newline after progress


def _extract_txt(zip_path: Path, filename: str, dest_dir: Path) -> Path:
    """Extract a single named file from a ZIP archive."""
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        match = next((n for n in names if Path(n).name == filename), None)
        if match is None:
            raise FileNotFoundError(
                f"{filename!r} not found in {zip_path.name}. Archive contents: {names}"
            )
        zf.extract(match, dest_dir)
        extracted = dest_dir / match
        # Flatten to dest_dir / filename if nested
        final = dest_dir / filename
        if extracted != final:
            extracted.rename(final)
        return final


def _get_file(url: str, zip_path: Path, txt_filename: str, dest_dir: Path) -> Path:
    """
    Return the path to an extracted text file, downloading and extracting
    only when the cached ZIP is stale or the text file is missing.
    """
    if not is_fresh(zip_path):
        print(f"Downloading {zip_path.name} …")
        _download_file(url, zip_path)
    else:
        print(f"Using cached {zip_path.name} (less than 7 days old)")

    txt_path = dest_dir / txt_filename
    if not txt_path.exists():
        print(f"Extracting {txt_filename} …")
        _extract_txt(zip_path, txt_filename, dest_dir)

    return txt_path


def download_ncsbe_files(dest_dir: Path) -> tuple[Path, Path]:
    """
    Ensure both NCSBE statewide text files exist in *dest_dir*, downloading
    and extracting only when the cached ZIPs are stale (> 7 days old).

    Returns:
        (ncvoter_path, ncvhis_path)
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    ncvoter_path = _get_file(
        NCVOTER_ZIP_URL,
        dest_dir / "ncvoter_Statewide.zip",
        NCVOTER_TXT_FILENAME,
        dest_dir,
    )
    ncvhis_path = _get_file(
        NCVHIS_ZIP_URL,
        dest_dir / "ncvhis_Statewide.zip",
        NCVHIS_TXT_FILENAME,
        dest_dir,
    )

    return ncvoter_path, ncvhis_path
