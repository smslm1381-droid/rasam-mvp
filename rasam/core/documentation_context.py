"""بخش‌های ضروری دانشِ هر مشتری در بازیابی حذف نمی‌شوند؛ محتوایشان همچنان ناامن است."""

from rasam.errors import UserFacingError

OPEN = "<!-- rasam:required -->"
CLOSE = "<!-- /rasam:required -->"


def required(text: str, limit: int) -> str:
    blocks = []
    remaining = text
    while OPEN in remaining:
        before, _, after = remaining.partition(OPEN)
        content, end, remaining = after.partition(CLOSE)
        if CLOSE in before or not end or OPEN in content:
            raise UserFacingError("علامت‌های بخش ضروری داکیومنت جفت نیستند؛ شروع و پایان بخش را بررسی کنید.")
        blocks.append(content.strip())
    if CLOSE in remaining:
        raise UserFacingError("پایان بخش ضروری داکیومنت بدون شروع آمده است.")
    result = "\n\n".join(block for block in blocks if block)
    if len(result) > limit:
        raise UserFacingError("بخش ضروری داکیومنت از ظرفیت دانش بیشتر است؛ آن را کوتاه‌تر کنید.")
    return result


def preserve(full: str, selected: str, limit: int) -> str:
    pinned = required(full, limit)
    if not pinned:
        return selected
    if pinned in selected and selected.index(pinned) + len(pinned) <= limit:
        return selected
    # متن ضروری اول می‌آید تا محدودسازی معمول پرامپت، آن را از انتها نبرد.
    room = limit - len(pinned) - 2
    optional = selected.replace(pinned, "")[:max(0, room)]
    return pinned + ("\n\n" + optional if optional else "")
