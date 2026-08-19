"""
Generate missing thumbnails for photos/<category>/*.jpg into photos/<category>/thumbs/.
Only processes files that don't already have a thumb with the same name.
"""
import subprocess
from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(__file__).parent
BAT_FILE = ROOT / "push.bat"
CATEGORIES = ["decup", "smola"]
THUMB_MAX_WIDTH = 480
JPEG_QUALITY = 72


def make_thumb(src: Path, dst: Path) -> None:
    with Image.open(src) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode != "RGB":
            img = img.convert("RGB")
        if img.width > THUMB_MAX_WIDTH:
            ratio = THUMB_MAX_WIDTH / img.width
            new_size = (THUMB_MAX_WIDTH, max(1, round(img.height * ratio)))
            img = img.resize(new_size, Image.LANCZOS)
        dst.parent.mkdir(parents=True, exist_ok=True)
        img.save(dst, "JPEG", quality=JPEG_QUALITY, optimize=True)


def main() -> None:
    total_made = 0
    for cat in CATEGORIES:
        cat_dir = ROOT / "photos" / cat
        thumbs_dir = cat_dir / "thumbs"
        if not cat_dir.is_dir():
            print(f"skip missing dir: {cat_dir}")
            continue
        thumbs_dir.mkdir(parents=True, exist_ok=True)

        sources = sorted(
            p for p in cat_dir.iterdir()
            if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg")
        )
        made = 0
        for src in sources:
            dst = thumbs_dir / src.name
            if dst.exists():
                continue
            make_thumb(src, dst)
            before = src.stat().st_size
            after = dst.stat().st_size
            print(f"[{cat}] {src.name}: {before//1024}KB -> {after//1024}KB")
            made += 1
        print(f"{cat}: {made} new thumb(s), {len(sources)} source(s) total")
        total_made += made

    print(f"done. {total_made} thumb(s) created.")


if __name__ == "__main__":
    main()

    answer = input("Пушить сразу? (да/нет): ").strip().lower()
    if answer in ("да", "", "+"):
        subprocess.run(["cmd.exe", "/c", str(BAT_FILE)], cwd=str(ROOT), check=False)
