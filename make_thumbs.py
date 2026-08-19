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
    cat_dirs = {cat: ROOT / "photos" / cat for cat in CATEGORIES}
    cat_dirs = {cat: d for cat, d in cat_dirs.items() if d.is_dir()}
    for cat, d in cat_dirs.items():
        (d / "thumbs").mkdir(parents=True, exist_ok=True)

    sources = {
        cat: sorted(
            p for p in d.iterdir()
            if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg")
        )
        for cat, d in cat_dirs.items()
    }

    # переносим "осиротевшие" тумбы вслед за перетащенными между категориями фото,
    # чтобы не пересжимать заново то, что уже сжато в другой папке
    moved = 0
    for cat, d in cat_dirs.items():
        thumbs_dir = d / "thumbs"
        for src in sources[cat]:
            dst = thumbs_dir / src.name
            if dst.exists():
                continue
            for other_cat, other_d in cat_dirs.items():
                if other_cat == cat:
                    continue
                stray = other_d / "thumbs" / src.name
                if stray.exists():
                    stray.rename(dst)
                    print(f"[{cat}] {src.name}: перенесён тумб из {other_cat}")
                    moved += 1
                    break

    made = 0
    for cat, d in cat_dirs.items():
        thumbs_dir = d / "thumbs"
        cat_made = 0
        for src in sources[cat]:
            dst = thumbs_dir / src.name
            if dst.exists():
                continue
            make_thumb(src, dst)
            before = src.stat().st_size
            after = dst.stat().st_size
            print(f"[{cat}] {src.name}: {before//1024}KB -> {after//1024}KB")
            cat_made += 1
        print(f"{cat}: {cat_made} new thumb(s), {len(sources[cat])} source(s) total")
        made += cat_made

    # чистим тумбы-сироты, чей исходник из папки исчез (удалён или перетащен и уже подхвачен выше)
    removed = 0
    for cat, d in cat_dirs.items():
        thumbs_dir = d / "thumbs"
        source_names = {p.name for p in sources[cat]}
        for thumb in thumbs_dir.iterdir():
            if thumb.is_file() and thumb.name not in source_names:
                thumb.unlink()
                print(f"[{cat}] удалён тумб-сирота: {thumb.name}")
                removed += 1

    print(f"done. {made} thumb(s) created, {moved} moved, {removed} orphan(s) removed.")


if __name__ == "__main__":
    main()

    answer = input("Пушить сразу? (да/нет): ").strip().lower()
    if answer in ("да", "", "+"):
        subprocess.run(["cmd.exe", "/c", str(BAT_FILE)], cwd=str(ROOT), check=False)
