from dataclasses import dataclass, field

import jsons

from async_collab.llm.llm_client import LLMAgentConfig
from logging_config import general_logger


@dataclass(frozen=True, eq=True, unsafe_hash=True)
class AgentConfig:
    main_user_id: str  # The name of the main user in the demo.
    tenant_id: str
    # Use `Union` to appease jsons
    model_config: LLMAgentConfig
    plugin_ids: tuple[str, ...] = ("system",)  # The names of the plugins to use.
    exemplar_ids: list[str] = field(
        default_factory=lambda: [
            "scenario_b_dialogue_001",
            "scenario_b_dialogue_002",
            "scenario_b_dialogue_003",
        ]
    )
    orchestrator_id: str = "event_driven_reactive"
    initial_message_text: str = "Hello, I'm here to help you as your Agent."

    @staticmethod
    def load(filename: str) -> "AgentConfig":
        """Load a config from a json file."""
        general_logger.info(f"Loading agent config from {filename}")
        with open(filename) as f:
            return jsons.loads(f.read(), cls=AgentConfig)
