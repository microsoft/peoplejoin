import asyncio
import hmac
import json
import os
import re
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

import jsons
from quart import Quart, abort, request, websocket
from werkzeug.datastructures import Headers

from async_collab.agent.agent_config import AgentConfig
from async_collab.agent.base_agent import Agent
from async_collab.core.person import Person
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

        def require_token(headers: Headers) -> None:
            token = os.environ.get("PEOPLEJOIN_API_TOKEN")
            if not token:
                abort(503, description="PEOPLEJOIN_API_TOKEN is not configured")
            supplied = headers.get("Authorization", "")
            if not hmac.compare_digest(supplied, "Bearer " + token):
                abort(401, description="Invalid API token")

        async def consume_and_produce(sender: Person | None) -> None:
            """Initiate the receiving and sending tasks for the agent relative to the given async context"""
            assert self.agent is not None
            producer = asyncio.create_task(self.agent.sending(sender))
            consumer = asyncio.create_task(self.agent.receiving(sender))
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
            require_token(websocket.headers)
            if self.agent is None:
                abort(409, description="Agent is not initialized")
            if user_id == "bridge":
                # The simulation bridge is trusted to relay any tenant participant.
                sender = None
            else:
                sender = self.agent.tenant.get_person_by_id(user_id)
                if sender is None:
                    abort(403, description="Unknown participant")
            general_logger.info(f"[API] ws called with user_id = {user_id}")
            try:
                await consume_and_produce(sender)
            except ValueError as exc:
                await websocket.send(json.dumps({"error": str(exc)}))
                await websocket.close(1008)

        # end point to load the given tenant
        @self.app.route("/init", methods=["POST"])
        async def init_setup():
            """
            Loads the tenant for the given session_id.
            """
            require_token(request.headers)
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
            require_token(request.headers)
            general_logger.info("[API] clear called")
            self.metadata = {}
            del self.agent
            self.agent = None
            return "No location to clear"

        @self.app.route("/save", methods=["POST"])
        async def save():
            """
            Saves the information in the session for the given user_id, assuming that user_id corresponds to a primary user.
            """
            require_token(request.headers)
            if self.agent is None:
                abort(409, description="Agent is not initialized")
            data = await request.get_json()
            if not isinstance(data, dict):
                abort(400, description="Expected JSON object")
            folder_path = data.get("folder_path", "workspace/logs")
            datum_id = data.get("datum_id", str(uuid4()))
            if not isinstance(folder_path, str) or not folder_path:
                abort(400, description="Invalid export folder")
            if not isinstance(datum_id, str) or not re.fullmatch(
                r"[A-Za-z0-9_-]+", datum_id
            ):
                abort(400, description="Invalid datum ID")
            export_root = Path(
                os.environ.get("PEOPLEJOIN_EXPORT_ROOT", "workspace")
            ).resolve()
            folder = Path(folder_path).resolve()
            if not folder.is_relative_to(export_root):
                abort(400, description="Export folder must be within export root")
            general_logger.info(
                f"[API] save called with folder_path = {folder_path} and datum_id = {datum_id}"
            )
            # create folder_path if not exists
            folder.mkdir(parents=True, exist_ok=True, mode=0o700)
            metadata = AsyncCollabDatumMetadata.from_processed_dict(self.metadata)
            datum = self.agent.compile_into_datum(datum_id=datum_id, metadata=metadata)
            general_logger.info("STATE SAVED")
            # save in json format at folder_path/{self.datum_id}.datum.json
            # json_str = jsons.dumps(datum.__dict__, indent=2)
            json_str = jsons.dumps(asdict(datum), indent=2)
            json_file = folder / f"{datum_id}.datum.json"
            text_file = folder / f"{datum_id}.conversation.txt"
            if json_file.exists() or text_file.exists():
                abort(409, description="Export already exists")
            # also save the yaml format using save_messages_from_datum_in_ui_yaml_format -- these can be loaded directly in the ui
            # Comment out this line, if experimenting with > 1 secondary users.
            datum_str = datum.all_message_and_action_history
            try:
                with os.fdopen(
                    os.open(json_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
                    "w",
                    encoding="utf-8",
                ) as f:
                    f.write(json_str)
                with os.fdopen(
                    os.open(text_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
                    "w",
                    encoding="utf-8",
                ) as f:
                    f.write("\n".join(datum_str))
            except FileExistsError:
                abort(409, description="Export already exists")
            general_logger.info(f"Saved datum to {json_file}")
            return "Saved at " + folder_path


def app(conf_name: str | None = None):
    print("Creating the app with conf_name = ", conf_name)
    return App(agent_conf_path=Path(conf_name) if conf_name is not None else None).app


if __name__ == "__main__":
    print("Running the app")
    app().run(port=8000)
