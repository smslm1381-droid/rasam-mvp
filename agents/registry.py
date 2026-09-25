"""انتخاب ایجنت دیتابیس از نوع ثبت‌شده در پروفایل مشتری."""

from __future__ import annotations

import config
from agents.mongo import MongoAgent
from agents.postgres import PostgresAgent

AGENTS = {
    "mongodb": MongoAgent,
    "postgresql": PostgresAgent,
}


def get_agent():
    agent_type = config.settings.customer.db_type
    agent_class = AGENTS.get(agent_type)
    if agent_class is None:
        raise ValueError(f"نوع دیتابیس «{agent_type}» پشتیبانی نمی‌شود.")
    return agent_class()