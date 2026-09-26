"""انتخاب ایجنت دیتابیس از نوع ثبت‌شده در پروفایل مشتری.

کلید هر ردیف همان `db_type` پروفایل مشتری است و هم‌نام پوشه‌ی آن دیتابیس.
"""

from __future__ import annotations

from rasam import config
from rasam.databases.base import DatabaseAgent
from rasam.databases.mongodb import MongoAgent
from rasam.databases.postgresql import PostgresAgent

AGENTS = {
    "mongodb": MongoAgent,
    "postgresql": PostgresAgent,
}


def get_agent() -> DatabaseAgent:
    agent_type = config.settings.customer.db_type
    agent_class = AGENTS.get(agent_type)
    if agent_class is None:
        raise ValueError(f"نوع دیتابیس «{agent_type}» پشتیبانی نمی‌شود.")
    return agent_class()
