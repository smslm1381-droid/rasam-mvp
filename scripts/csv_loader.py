"""خواندن CSVهای دمو، مشترک بین همه‌ی اسکریپت‌های seed.

تا وقتی فقط مونگو بود، این کد داخل `seed_mongo.py` بود. MySQL مصرف‌کننده‌ی دوم
است و قاعده‌ی «انتزاع فقط وقتی دومین مورد آمد» اینجا بیرونش می‌کشد: هر دو
دیتابیس **دقیقاً همان ردیف‌ها** را می‌بینند، پس اگر جواب دو دیتابیس فرق کرد،
تقصیر آداپتور است نه داده (تصمیم ۶۵).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def table_name(path: Path) -> str:
    """`solar_telemetry.inverter_data.csv` ← `inverter_data`.

    فایل‌های دامپ نام دیتابیس را هم جلوی نام کالکشن دارند. آخرین تکه همیشه نام
    کالکشن یا جدول است؛ همین قاعده برای فایلی به نام `inverter_data.csv` هم کار می‌کند.
    """
    return path.stem.rsplit(".", 1)[-1]


def read_frame(path: Path) -> pd.DataFrame:
    """یک CSV، بدون ستونی که در کل فایل خالی است (مثل `fa_al_message`).

    ستون پوچ اگر وارد شود، در schema می‌آید و مدل روی فیلد پوچ حساب باز می‌کند.
    """
    return pd.read_csv(path, low_memory=False).dropna(axis="columns", how="all")


def records(frame: pd.DataFrame) -> list[dict]:
    """ردیف‌ها به‌صورت dict، **با سلول خالی حذف‌شده** نه `NaN`.

    `NaN` در مونگو یک عددِ واقعی است و `$avg` و `$max` را بی‌صدا خراب می‌کند؛
    در MySQL هم `NaN` پذیرفته نمی‌شود. «نبود مقدار» باید نبود بماند (`NULL`).
    """
    return [
        {key: value for key, value in row.items() if pd.notna(value)}
        for row in frame.to_dict("records")
    ]
