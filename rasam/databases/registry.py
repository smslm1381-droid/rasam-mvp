"""انتخاب ایجنت دیتابیس از نوع ثبت‌شده در پروفایل مشتری.

کلید هر ردیف همان `db_type` پروفایل مشتری است و هم‌نام پوشه‌ی آن دیتابیس.
"""

from __future__ import annotations

from rasam import config
from rasam.customer import CustomerProfile
from rasam.databases.base import DatabaseAgent
from rasam.databases.mongodb import MongoAgent
from rasam.databases.postgresql import PostgresAgent

AGENTS = {
    "mongodb": MongoAgent,
    "postgresql": PostgresAgent,
}


def check_db_type(profile: CustomerProfile) -> None:
    """نوع دیتابیس ناشناخته همان لحظه‌ی راه‌اندازی خطا بدهد، نه در اولین سوال.

    در `config` نیست چون رجیستری خودش `config` را import می‌کند و دور می‌ساخت؛
    `core/graph.py` هنگام import آن را صدا می‌زند، یعنی پیش از اولین سوال.
    """
    if profile.db_type not in AGENTS:
        raise config.ConfigError(
            f"نوع دیتابیس «{profile.db_type}» در پروفایل مشتری «{profile.name}» "
            f"پشتیبانی نمی‌شود. نوع‌های موجود: {', '.join(sorted(AGENTS))}."
        )


def get_agent() -> DatabaseAgent:
    agent_type = config.settings.customer.db_type
    agent_class = AGENTS.get(agent_type)
    if agent_class is None:
        raise ValueError(f"نوع دیتابیس «{agent_type}» پشتیبانی نمی‌شود.")
    return agent_class()
