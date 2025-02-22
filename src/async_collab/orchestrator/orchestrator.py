from abc import ABC, abstractmethod

from async_collab.agent.agent_config import AgentConfig
from async_collab.core.message import Message
from async_collab.llm.llm_client import LLMClient
from async_collab.orchestrator.prompt_builder import PromptBuilder
from async_collab.plugins.all_plugins import plugins_by_id
from async_collab.plugins.plugin import Plugin
from async_collab.tenant.tenant import Tenant
from async_collab.tenant.tenant_loaders import TenantLoader


class Orchestrator(ABC):
    def __init__(
        self,
        agent_config: AgentConfig,
        tenant: Tenant | None = None,
        send_queue: list[Message] | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        plugin_names = agent_config.plugin_ids
        exemplar_ids = agent_config.exemplar_ids
        if tenant is not None:
            self.tenant: Tenant = tenant
            assert tenant.tenant_id == agent_config.tenant_id
        else:
            self.tenant: Tenant = TenantLoader.from_id(agent_config.tenant_id)
        plugins: list[Plugin] = [
            plugins_by_id[plugin_name].get_plugin(agent_config, self.tenant, send_queue)
            for plugin_name in plugin_names
        ]
        self.plugins: list[Plugin] = plugins
        self.plugin_name_to_plugin = {plugin.plugin_name: plugin for plugin in plugins}
        self.init_prompt_builder(exemplar_ids)
        self.llm_client = llm_client

    def init_prompt_builder(self, exemplar_ids: list[str]):
        self.prompt_builder: PromptBuilder = PromptBuilder(self.plugins, exemplar_ids)

    def reset(self):
        self.prompt_builder.reset()

    @abstractmethod
    def on_event(self, event: Message) -> str | None:
        pass
