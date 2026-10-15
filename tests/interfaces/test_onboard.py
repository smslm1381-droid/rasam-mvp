"""تست ابزار تحویل مشتری، بدون ترمینال: ورودی و خروجی تزریق می‌شوند."""

from __future__ import annotations

import pytest

from rasam import config, customer, onboard
from rasam.databases import registry


class FakeAgent:
    """ایجنت جعلی؛ تا بخش‌هایی از ابزار که به دیتابیس واقعی ربط ندارند مستقل سنجیده شوند."""

    def __init__(self, connection_uri=None, database=None):
        self.connection_uri, self.database = connection_uri, database

    def list_sources(self):
        return ["alpha", "beta", "billing"]

    def list_fields(self, source):
        return {"alpha": ["a1", "a2"], "beta": ["b1"], "billing": ["card"]}[source]


class Script:
    """پاسخ‌های از پیش‌تعیین‌شده؛ و همه‌ی چیزی که ابزار چاپ کرد."""

    def __init__(self, *answers: str):
        self.answers, self.said = list(answers), []

    def ask(self, prompt: str) -> str:
        return self.answers.pop(0)

    def say(self, text: str) -> None:
        self.said.append(text)

    @property
    def output(self) -> str:
        return "\n".join(self.said)


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """پوشه‌ی مشتری‌های موقت، یک دیتابیس جعلی ثبت‌شده، و متغیر اتصال."""
    monkeypatch.setattr(config, "CUSTOMERS_DIR", tmp_path)
    monkeypatch.setattr(registry, "AGENTS", {"fakedb": FakeAgent})
    monkeypatch.setenv("RASAM_TRIAL_DB_URI", "fakedb://reader:s3cr3t-pass@host/trial")
    return tmp_path


def run(script: Script) -> int:
    return onboard.run_new(ask=script.ask, say=script.say)


def good_script(sources: str = "1,2") -> Script:
    return Script("trial", "1", "", "trial_db", sources)


def test_a_new_customer_folder_is_built_from_the_answers(workspace):
    script = good_script()
    assert run(script) == 0
    folder = workspace / "trial"
    assert sorted(path.name for path in folder.iterdir()) == sorted(onboard.TEMPLATE_FILES)

    profile = customer.load_profile("trial", workspace)  # پروفایل ساخته‌شده معتبر است
    assert profile.db_type == "fakedb" and profile.database == "trial_db"
    assert profile.connection_env == "TRIAL_DB_URI"
    assert profile.allowed_sources == {"alpha", "beta"}


def test_unselected_sources_are_left_out_everywhere(workspace):
    """منبعی که انتخاب نشد (`billing`) نه در فهرست سفید است نه در مستندات."""
    run(good_script("1,2"))
    folder = workspace / "trial"
    assert all("billing" not in (folder / name).read_text(encoding="utf-8")
               for name in onboard.TEMPLATE_FILES)


def test_the_connection_string_is_never_written_or_printed(workspace):
    """مهم‌ترین تست: رشته‌ی اتصال و رمزش هیچ‌جا نمی‌آید."""
    script = good_script()
    run(script)
    texts = [script.output] + [(path).read_text(encoding="utf-8")
                               for path in (workspace / "trial").iterdir()]
    for text in texts:
        assert "s3cr3t-pass" not in text and "fakedb://" not in text and "reader" not in text


def test_the_domain_knowledge_is_marked_for_a_human_not_guessed(workspace):
    run(good_script())
    documentation = (workspace / "trial" / "documentation.md").read_text(encoding="utf-8")
    assert onboard.TODO_MARKER in documentation
    assert "`a1`, `a2`" in documentation  # فیلدها نوشته شده‌اند، معنایشان نه


def test_nothing_is_selected_by_default(workspace):
    script = Script("trial", "1", "", "trial_db", "")
    assert run(script) == 1
    assert not (workspace / "trial").exists()


@pytest.mark.parametrize("selection", ["9", "0", "x", "1,9"])
def test_an_invalid_selection_builds_nothing(workspace, selection):
    assert run(good_script(selection)) == 1
    assert not (workspace / "trial").exists()


def test_a_missing_connection_variable_is_explained_without_asking_for_the_value(workspace, monkeypatch):
    monkeypatch.delenv("RASAM_TRIAL_DB_URI")
    script = Script("trial", "1", "")
    assert run(script) == 1
    assert "RASAM_TRIAL_DB_URI" in script.output and "نمی‌پرسد" in script.output


def test_a_bad_name_is_refused(workspace):
    assert run(Script("Bad Name")) == 1


def test_an_existing_customer_is_never_overwritten(workspace):
    (workspace / "trial").mkdir()
    (workspace / "trial" / "keep.txt").write_text("x")
    assert run(good_script()) == 1
    assert (workspace / "trial" / "keep.txt").exists()


def test_a_database_type_without_an_adapter_points_to_the_guide(workspace):
    script = Script("trial", "oracle")
    assert run(script) == 1
    assert "docs/adding-a-database.md" in script.output


def test_a_connection_failure_does_not_leak_the_server_message(workspace, monkeypatch):
    class Broken(FakeAgent):
        def list_sources(self):
            raise ConnectionError("cannot reach fakedb://reader:s3cr3t-pass@host")

    monkeypatch.setattr(registry, "AGENTS", {"fakedb": Broken})
    script = Script("trial", "1", "", "trial_db")
    assert run(script) == 1
    assert "s3cr3t-pass" not in script.output and "ConnectionError" in script.output


def test_a_failure_while_writing_leaves_no_half_built_folder(workspace, monkeypatch):
    class Broken(FakeAgent):
        def list_fields(self, source):
            raise RuntimeError("boom")

    monkeypatch.setattr(registry, "AGENTS", {"fakedb": Broken})
    assert run(good_script()) == 1
    assert not (workspace / "trial").exists()


# --- روی مونگوی واقعی -------------------------------------------------------

def test_the_real_mongo_agent_lists_sources_and_fields_without_the_active_customer():
    from rasam.databases.mongodb import MongoAgent

    agent = MongoAgent(connection_uri=config.settings.connection_uri,
                       database=config.settings.database)
    try:
        sources = agent.list_sources()
    except Exception as error:  # noqa: BLE001
        pytest.skip(f"مونگوی محلی در دسترس نیست: {type(error).__name__}")
    assert "inverter_data" in sources
    assert "int_temp" in agent.list_fields("inverter_data")
