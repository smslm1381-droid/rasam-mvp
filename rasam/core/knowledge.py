"""دانش دامنه‌ی هر مشتری: خواندن فایل‌هایش، و شاخص معنایی برای وقتی که زیاد شد.

دانش در پوشه‌ی خودِ مشتری است (`customers/<نام>/`)، نه در کد: واژگان فارسی،
تله‌های داده، نمونه‌های «سوال ← کوئری» و توضیح فیلدها. کد این فایل برای همه‌ی
مشتری‌ها یکی است؛ فقط پوشه‌ای که می‌خواند عوض می‌شود.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

import chromadb
import yaml
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from rasam import config

DOCUMENTATION_FILE = "documentation.md"
EXAMPLES_FILE = "examples.yaml"
FIELD_NOTES_FILE = "field_notes.yaml"

DIMENSIONS = 128
COLLECTIONS = ("schema", "documentation", "examples")
TOKEN_RE = re.compile(r"[\w\u0600-\u06ff]+", re.UNICODE)


def _customer_file(name: str) -> Path:
    return config.settings.customer.directory / name


@lru_cache(maxsize=1)
def documentation_text() -> str:
    """واژگان فارسی، توضیح کالکشن‌ها و تله‌های داده. مشتری بدون این فایل، متن خالی."""
    path = _customer_file(DOCUMENTATION_FILE)
    return path.read_text(encoding="utf-8").strip() if path.is_file() else ""


@lru_cache(maxsize=1)
def examples() -> list[dict]:
    """نمونه‌های «سوال ← کوئری» مشتری، خام."""
    path = _customer_file(EXAMPLES_FILE)
    if not path.is_file():
        return []
    return yaml.safe_load(path.read_text(encoding="utf-8")) or []


def examples_text(format_example: Callable[[dict], str]) -> str:
    """نمونه‌ها به‌صورت متن آماده‌ی پرامپت.

    خواندن فایل در هسته است ولی **تبدیل یک نمونه به متن** مال ایجنت دیتابیس
    است (`format_example`): شکل کوئری را فقط او می‌شناسد، و قالب نمونه باید
    همان قالب پاسخی باشد که از مدل می‌خواهیم.
    """
    return "\n\n".join(format_example(item) for item in examples())


@lru_cache(maxsize=1)
def field_notes() -> dict[str, str]:
    """یادداشت کوتاه برای فیلدهایی که مدل درباره‌شان اشتباه می‌کند.

    این یادداشت‌ها کنار خط همان فیلد در متن schema می‌نشینند. قبلاً داخل کد
    مونگو بودند، یعنی هر مشتری مونگوی تازه یادداشت‌های نیروگاه خورشیدی را
    می‌گرفت. حالا مال پوشه‌ی مشتری‌اند.
    """
    path = _customer_file(FIELD_NOTES_FILE)
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


class MultilingualEmbedding(EmbeddingFunction[Documents]):
    """بردار قطعی واژه‌ها و n-gramها؛ بدون دانلود مدل و مناسب متن فارسی."""

    def __init__(self) -> None:
        pass

    def __call__(self, input: Documents) -> Embeddings:
        return [self._embed(text) for text in input]

    @staticmethod
    def name() -> str:
        return "rasam-multilingual-hash"

    def get_config(self) -> dict[str, str]:
        return {"name": self.name()}

    @classmethod
    def build_from_config(cls, config: dict[str, str]) -> "MultilingualEmbedding":
        return cls()

    @staticmethod
    def _embed(text: str) -> list[float]:
        vector = [0.0] * DIMENSIONS
        tokens = TOKEN_RE.findall(text.lower())
        features = tokens + [token[i:i + 3] for token in tokens for i in range(len(token) - 2)]
        for feature in features:
            digest = hashlib.sha256(feature.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % DIMENSIONS
            vector[index] += 1.0
        norm = sum(value * value for value in vector) ** 0.5 or 1.0
        return [value / norm for value in vector]


class KnowledgeStore:
    """سه مجموعه‌ی دانش را برای یک مشتری نگه می‌دارد و جست‌وجو می‌کند."""

    def __init__(self, customer: str, persist_dir: Path):
        client = chromadb.PersistentClient(path=str(persist_dir / customer))
        embedding = MultilingualEmbedding()
        self._collections = {
            name: client.get_or_create_collection(name=name, embedding_function=embedding)
            for name in COLLECTIONS
        }

    def rebuild(self, schema: str, knowledge_dir: Path) -> None:
        """شاخص را از schema، مستندات و مثال‌های فعلی بازسازی می‌کند."""
        self._replace("schema", _schema_documents(schema))
        self._replace("documentation", _documentation_documents(knowledge_dir))
        self._replace("examples", _example_documents(knowledge_dir))

    def select(self, question: str, full: dict[str, str], budget: int) -> dict[str, str]:
        """دانشی که به پرامپت می‌رود: کامل تا وقتی جا می‌شود، وگرنه مرتبط‌ترین.

        بازیابی معنایی برای مشتری‌ای ساخته شد که ۵۰ کالکشن دارد و schemaاش در
        پرامپت جا نمی‌شود. برای مشتری فعلی با چهار کالکشن، *باختن* است نه بردن:
        روی داده‌ی واقعی سنجیده شد که برای سوال «میانگین توان راکتیو اینورترها»
        هم schema کالکشن `inverter_data` از پرامپت می‌افتاد و هم تله‌ی
        `tot_reactive_pow` — یعنی دقیقاً همان دو چیزی که بدون آن‌ها جواب این
        سوال غلط است.

        پس قاعده این است: تا وقتی همه‌ی دانش در بودجه جا می‌شود، هیچ‌چیز حذف
        نمی‌شود. بازیابی وقتی وارد می‌شود که چاره‌ای نباشد — و آن‌وقت هم
        کم‌کردن دانش یک انتخاب آگاهانه است، نه اتفاقی که کسی متوجهش نشود.
        """
        if sum(len(text) for text in full.values()) <= budget:
            return full
        return self.retrieve(question)

    def retrieve(self, question: str, limit: int = 3) -> dict[str, str]:
        """مرتبط‌ترین قطعه از هر نوع دانش را به متن آماده‌ی پرامپت تبدیل می‌کند."""
        results = {}
        for name, collection in self._collections.items():
            if collection.count() == 0:
                results[name] = ""
                continue
            found = collection.query(query_texts=[question], n_results=limit)
            results[name] = "\n\n".join(found["documents"][0])
        return results

    def _replace(self, name: str, documents: list[dict[str, Any]]) -> None:
        collection = self._collections[name]
        if collection.count():
            collection.delete(ids=collection.get()["ids"])
        if not documents:
            return
        collection.add(
            ids=[item["id"] for item in documents],
            documents=[item["text"] for item in documents],
            metadatas=[item["metadata"] for item in documents],
        )


def _schema_documents(schema: str) -> list[dict[str, Any]]:
    chunks = [chunk.strip() for chunk in schema.split("\n\n") if chunk.strip()]
    return [_document(f"schema-{index}", chunk, {"kind": "schema"})
            for index, chunk in enumerate(chunks)]


def _documentation_documents(directory: Path) -> list[dict[str, Any]]:
    path = directory / "documentation.md"
    if not path.is_file():
        return []
    chunks = [chunk.strip() for chunk in path.read_text(encoding="utf-8").split("\n\n")]
    return [_document(f"documentation-{index}", chunk, {"kind": "documentation"})
            for index, chunk in enumerate(chunks) if chunk]


def _example_documents(directory: Path) -> list[dict[str, Any]]:
    path = directory / "examples.yaml"
    if not path.is_file():
        return []
    examples = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return [_document(
        f"example-{index}",
        f"Q: {item['question']}\nWhy: {item.get('why', '')}\nA: {item['source']} {item['query']}",
        {"kind": "examples", "source": item["source"]},
    ) for index, item in enumerate(examples)]


def _document(identifier: str, text: str, metadata: dict[str, str]) -> dict[str, Any]:
    return {"id": identifier, "text": text, "metadata": metadata}
