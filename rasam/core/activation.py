"""تعویض مشتری در اجرای رومیزی، همراه با دورریختن حافظهٔ مشتری قبلی."""

import sys
from rasam import config
from rasam.databases import registry


def activate(name):
    settings = config._load(name, require_model=False)
    registry.reset_caches()
    config.settings = settings
    knowledge = sys.modules.get("rasam.core.knowledge")
    if knowledge is not None:
        knowledge.documentation_text.cache_clear()
        knowledge.examples.cache_clear()
        knowledge.field_notes.cache_clear()
    graph = sys.modules.get("rasam.core.graph")
    if graph is not None:
        graph._knowledge_store.cache_clear()
        graph._GRAPH = graph.build_graph(settings.customer.capabilities)
    llm = sys.modules.get("rasam.core.llm")
    if llm is not None:
        llm._client.cache_clear()
