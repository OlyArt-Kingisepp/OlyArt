"""
Generate missing thumbnails for photos/<category>/*.jpg into photos/<category>/thumbs/.
Only processes files that don't already have a thumb with the same name.
"""
import json
import re
import subprocess
from datetime import date
from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(__file__).parent
BAT_FILE = ROOT / "push.bat"
JSON_FILE = ROOT / "gallery-data.json"
CATEGORIES = ["decup", "smola"]
THUMB_MAX_WIDTH = 480
JPEG_QUALITY = 72
CATEGORY_TITLES = {"decup": "Декупаж", "smola": "Смола"}
NEW_WINDOW_DAYS = 7
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


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


def photo_date(path: Path) -> str:
    m = DATE_RE.search(path.name)
    if m:
        return m.group(1)
    return date.fromtimestamp(path.stat().st_mtime).isoformat()


def photo_aspect(path: Path) -> float:
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        return round(img.width / img.height, 3)


def sync_gallery_json(cat_dirs: dict[str, Path], sources: dict[str, list[Path]]) -> None:
    """Синхронизирует gallery-data.json с реальным состоянием photos/:
    - чинит пути записей, чьи файлы перетащили между категориями вручную
    - добавляет записи для новых файлов, которых ещё нет в json
    - пересчитывает isNew по дате (бейдж живёт NEW_WINDOW_DAYS, затем гаснет сам)
    - сортирует список по дате (новые сверху, без ручного закрепления)
    """
    if not JSON_FILE.is_file():
        print("gallery-data.json не найден, пропуск синхронизации")
        return

    with open(JSON_FILE, encoding="utf-8") as f:
        data = json.load(f)

    today = date.today()
    fixed = 0
    missing = 0

    for it in data:
        full = it.get("full", "")
        if not full or (ROOT / full).is_file():
            continue

        name = Path(full).name
        found_cat = next((cat for cat, d in cat_dirs.items() if (d / name).is_file()), None)
        if not found_cat:
            print(f"[json] id={it.get('id')} файл не найден нигде: {name}")
            missing += 1
            continue

        old_cat = next((cat for cat in CATEGORIES if f"photos/{cat}/" in full), None)
        it["full"] = f"photos/{found_cat}/{name}"
        it["src"] = f"photos/{found_cat}/thumbs/{name}"

        title = it.get("title", "")
        if old_cat and CATEGORY_TITLES.get(old_cat) and title.startswith(CATEGORY_TITLES[old_cat]):
            it["title"] = title.replace(CATEGORY_TITLES[old_cat], CATEGORY_TITLES[found_cat], 1)

        print(f"[json] id={it.get('id')} {name}: {old_cat} -> {found_cat}")
        fixed += 1

    known_names = {Path(it["full"]).name for it in data if it.get("full")}
    next_id = (max((it["id"] for it in data), default=0) + 1)
    added = 0
    for cat, files in sources.items():
        for src in files:
            if src.name in known_names:
                continue
            item_date = photo_date(src)
            data.append({
                "id": next_id,
                "title": f"{CATEGORY_TITLES.get(cat, cat.title())} — авторская работа",
                "date": item_date,
                "isNew": (today - date.fromisoformat(item_date)).days <= NEW_WINDOW_DAYS,
                "aspect": photo_aspect(src),
                "src": f"photos/{cat}/thumbs/{src.name}",
                "full": f"photos/{cat}/{src.name}",
            })
            print(f"[json] добавлена новая запись id={next_id}: {cat}/{src.name} ({item_date})")
            known_names.add(src.name)
            next_id += 1
            added += 1

    for it in data:
        it["isNew"] = (today - date.fromisoformat(it["date"])).days <= NEW_WINDOW_DAYS

    data.sort(key=lambda it: (it["date"], it["id"]), reverse=True)

    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"gallery-data.json: {fixed} путь(ей) исправлено, {added} новых записей добавлено, {missing} файл(ов) не найдено")


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

    sync_gallery_json(cat_dirs, sources)


if __name__ == "__main__":
    main()

    answer = input("Пушить сразу? (да/нет): ").strip().lower()
    if answer in ("да", "", "+"):
        subprocess.run(["cmd.exe", "/c", str(BAT_FILE)], cwd=str(ROOT), check=False)
