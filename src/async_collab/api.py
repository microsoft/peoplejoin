import asyncio
import json
import os
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

import jsons
from quart import Quart, request

from async_collab.agent.agent_config import AgentConfig
from async_collab.agent.base_agent import Agent
from async_collab.orchestrator.datum import AsyncCollabDatumMetadata
from logging_config import general_logger


class App:
    """
    App is the core entrypoint of the backend of the application.
    Broadly, it initializes the state management in the form of a SessionBroker, it loads the relevant AgentConfig, and it then initializes the actual behavior in the form of a DemoAgent.
    """

    metadata: dict[str, str]
    agent: Agent | None  # only one agent for now;
    # can easily extend the setup to introduce session_id
    # agents: dict[str, Agent] # for multiple agents; session_id -> Agent
    # metadata: dict[str, dict[str, str]] # for multiple agents; session_id -> metadata

    def __init__(self, agent_conf_path: Path | None = None):
        self.app = Quart(__name__)
        self.metadata = {}
        if agent_conf_path is not None:
            config = AgentConfig.load(str(agent_conf_path))
            self.agent = Agent(agent_config=config)
            general_logger.info(f"[App.init()]: self.agent = {self.agent}")
        else:
            self.agent = None

        async def consume_and_produce() -> None:
            """Initiate the receiving and sending tasks for the agent relative to the given async context"""
            assert self.agent is not None
            producer = asyncio.create_task(self.agent.sending())
            consumer = asyncio.create_task(self.agent.receiving())
            try:
                await asyncio.gather(consumer, producer)
            finally:
                consumer.cancel()
                producer.cancel()

        @self.app.websocket("/ws/<user_id>")
        async def ws(user_id: str) -> None:
            """
            Initiates a user session for the given user_id as a primary user.
            This should be the default choice in general - it initializes the system
            to undertake actions on behalf of that user as that user's agent.
            """
            general_logger.info(f"[API] ws called with user_id = {user_id}")
            await consume_and_produce()

        # end point to load the given tenant
        @self.app.route("/init", methods=["POST"])
        async def init_setup():
            """
            Loads the tenant for the given session_id.
            """
            general_logger.info("[API] init_setup called")
            data = await request.get_json()
            metadata = data.get("metadata")
            if metadata is not None:
                self.metadata = json.loads(metadata)
                general_logger.info(
                    f"[API] init_setup called with metadata = {metadata}"
                )
            agent_config_path = data.get("agent_config_path")
            assert agent_config_path is not None
            # TODO: construct Agent; which implicitly builds orchestrator, tenant, plugins, etc.
            self.agent = Agent(AgentConfig.load(agent_config_path))
            general_logger.info(
                f"[API] init_setup called with agent_config_path = {agent_config_path}"
            )
            self.agent.reset()
            general_logger.info(
                f"[API] init_setup called with agent_config_path = {agent_config_path}"
            )
            return "Loaded Agent and reset the state"

        @self.app.route("/clear")
        async def clear():
            """
            Clears the session state associated with the given user_id, assuming that user_id corresponds to a primary user.
            """
            general_logger.info("[API] clear called")
            self.metadata = {}
            del self.agent
            self.agent = None
            return "No location to clear"

        @self.app.route("/save")
        async def save():
            """
            Saves the information in the session for the given user_id, assuming that user_id corresponds to a primary user.
            """
            folder_path = request.args.get("folder_path", "logs")
            datum_id = request.args.get("datum_id", str(uuid4()))
            general_logger.info(
                f"[API] save called with folder_path = {folder_path} and datum_id = {datum_id}"
            )
            # create folder_path if not exists
            os.makedirs(folder_path, exist_ok=True)
            metadata = AsyncCollabDatumMetadata.from_processed_dict(self.metadata)
            assert self.agent is not None
            datum = self.agent.compile_into_datum(datum_id=datum_id, metadata=metadata)

            # dump agent.orchestrator.prompt_builder.messages or agent_logger.repl_and_messages

            # Save using prompt_builder.messages with serialize_message to avoid AttributeError
            def serialize_message(m):
                if isinstance(m, dict):
                    return m
                if hasattr(m, "__dict__"):
                    d = dict(m.__dict__)
                    if "function_call" in d and hasattr(d["function_call"], "__dict__"):
                        d["function_call"] = dict(d["function_call"].__dict__)
                    return d
                return str(m)

            with open(f"{folder_path}/{datum_id}.messages.json", "w") as f:
                json.dump(
                    [
                        serialize_message(m)
                        for m in self.agent.orchestrator.prompt_builder.messages
                    ],
                    f,
                    indent=2,
                )
            general_logger.info(
                f"Saved messages to {folder_path}/{datum_id}.messages.json"
            )

            general_logger.info("STATE SAVED")
            # save in json format at folder_path/{self.datum_id}.datum.json
            json_str = jsons.dumps(asdict(datum), indent=2)
            with open(f"{folder_path}/{datum_id}.datum.json", "w") as f:
                f.write(json_str)
            general_logger.info(f"Saved datum to {folder_path}/{datum_id}.datum.json")
            # also save the yaml format using save_messages_from_datum_in_ui_yaml_format -- these can be loaded directly in the ui
            datum_str = datum.all_message_and_action_history
            with open(
                f"{folder_path}/{datum_id}.conversation.txt", "w", encoding="utf-8"
            ) as f:
                f.write("\n".join(datum_str))
            return "Saved at " + folder_path


def app(conf_name: str | None = None):
    print("Creating the app with conf_name = ", conf_name)
    return App(agent_conf_path=Path(conf_name) if conf_name is not None else None).app


if __name__ == "__main__":
    print("Running the app")
    app().run(port=8000)
