import asyncio
import dataclasses
import json
import os
import sys
from contextlib import contextmanager
from threading import Timer

import httpx
import jsons
import websockets

from async_collab.core.bot import Bot
from async_collab.core.message import Message, SessionCompleted
from async_collab.core.person import Person
from async_collab.llm.llm_client_service import get_llm_client
from async_collab.orchestrator.datum import AsyncCollabDatumMetadata
from async_collab.settings import demo_settings
from async_collab.tenant.tenant import Tenant
from async_collab.tenant.tenant_loaders import TenantLoader
from experimentation.sim_hitl_exp_config import ExpSimulHitlConfig
from experimentation.simulated_user import UserSimulator
from logging_config import simulated_user_logger


class TimeoutException(Exception):
    pass


# https://stackoverflow.com/questions/366682/how-to-limit-execution-time-of-a-function-call-in-python
@contextmanager
def time_limit(seconds):
    def timeout_handler():
        raise TimeoutException("Timed out!")

    timer = Timer(seconds, timeout_handler)
    timer.start()
    try:
        yield
    finally:
        timer.cancel()


class DialogManager:

    """
    A simple dialog manager that managers a conversation between users and a bot (running on a server)
    - send out any initial messages
    - wait for a message from the bot
    - redirect the bot's message to the appropriate user
    - relay the user's response to the bot

    Supports two modes:
    - simulation: the user's responses are generated using a language model
    - hitl: the bot's responses are generated using a language model, but the user's responses are manually entered via the terminal

    Limitations:
    - a limitation is the assumption on turn taking -- a user can respond once and only when bot sends a message.
    """

    def __init__(self, exp_config: ExpSimulHitlConfig) -> None:
        # register_codec()
        self.tenant: Tenant = TenantLoader.from_id(exp_config.tenant_id)
        self.participants: tuple[Person, ...] = self.tenant.people
        simulated_user_logger.info(
            f"[experiment_with_hitl_or_simulation] Participants: {self.participants}"
        )
        person = self.tenant.get_person_by_id(exp_config.agent_config.main_user_id)
        assert person is not None
        self.main_user: Person = person
        simulated_user_logger.info(
            f"[experiment_with_hitl_or_simulation] Main User: {self.main_user}"
        )
        self.bot: Bot = Bot(
            owner=self.main_user
        )  # TODO: can move bot property from Agent to Config to avoid this duplication
        self.llm_client = get_llm_client(
            # default_model="dev-gpt-4-turbo"
            default_model="dev-gpt-4o-2024-05-13"
        )  # Setting model here: TODO: make it a param; "dev-gpt-4o-2024-05-13", "dev-gpt-4-turbo"
        participant_id_to_hitl_mode = exp_config.participant_id_to_hitl_mode
        simulated_user_logger.info(
            f"[experiment_with_hitl_or_simulation] Loading mock tenant from config {exp_config.tenant_id}"
        )
        simulated_user_logger.info(
            "[experiment_with_hitl_or_simulation] Creating participant simulators"
        )
        person_id_to_document_collection = self.tenant.person_id_to_document_collection
        self.participant_simulators = {
            participant.person_id: UserSimulator(
                participant,
                exp_config.participant_descriptions.get(
                    participant.person_id,
                    "One of the participants in the conversation.",
                ),
                self.llm_client,
                hitl=participant_id_to_hitl_mode.get(
                    participant.person_id, False
                ),  # default to False
                provided_instruction=exp_config.participant_instructions.get(
                    participant.person_id, None
                ),  # if None, DEFAULT_INSTRUCTIONS will be used
                provided_instruction_name=exp_config.default_instructions_file_name
                if exp_config.participant_instructions.get(participant.person_id, None)
                is None
                else None,
                doc_search=self.tenant.person_id_to_document_collection.get(
                    participant.person_id, None
                )
                if person_id_to_document_collection
                else None,
                stop_token=exp_config.stop_token,
                is_main_user=(participant.person_id == self.main_user.person_id),
            )
            for participant in self.participants
        }
        self.datum_id = exp_config.datum_id

    async def call_clear_endpoint(self):
        async with httpx.AsyncClient() as client:
            print("demo_settings.clear_url = ", demo_settings.get_clear_url())
            response = await client.get(demo_settings.get_clear_url())

            # Handle the response as needed
            if response.status_code == 200:
                print("Clear endpoint called successfully")
                simulated_user_logger.info(
                    "[experiment_with_hitl_or_simulation] Clear endpoint called successfully"
                )
            else:
                print(
                    f"Failed to call clear endpoint. Status code: {response.status_code}"
                )
                simulated_user_logger.info(
                    f"[experiment_with_hitl_or_simulation] Failed to call clear endpoint. Status code: {response.status_code}"
                )

    # set_metadata
    async def init(
        self, agent_config_path: str, metadata: AsyncCollabDatumMetadata | None
    ):
        async with httpx.AsyncClient() as client:
            print(
                "demo_settings.get_init_url() = ",
                demo_settings.get_init_url(),  # agent_config_path),
            )
            data = {"agent_config_path": agent_config_path}
            if metadata is not None:
                data["metadata"] = jsons.dumps(dataclasses.asdict(metadata))
                print("metadata = ", metadata)
                print("data[metadata] = ", data["metadata"])
            headers = {"Content-Type": "application/json"}
            response = await client.post(
                demo_settings.get_init_url(),
                json=data,
                headers=headers,  # agent_config_path
            )
            # Handle the response as needed
            if response.status_code == 200:
                print("Initiated new session successfully")
            else:
                print(
                    f"Failed to initiate session. Status code: {response.status_code}"
                )
                print(response.text)

    async def run(self, save_folder: str = "logs/"):
        conn_url = demo_settings.get_connect_url(self.main_user.person_id)
        print("Connecting to the server at ", conn_url)
        simulated_user_logger.info(
            f"[experiment_with_hitl_or_simulation] Connecting to the server at {conn_url}"
        )

        # clear the api using get_clear_url
        await self.call_clear_endpoint()

        # call init with agent_config_path
        await self.init(exp_config.agent_config_path, exp_config.metadata)

        async with websockets.connect(conn_url, ping_interval=None) as websocket:
            print("Connected to the server")

            try:
                while True:
                    # Receive data from the server
                    # but put a timer on it
                    # response_str: str = await websocket.recv()  # type: ignore
                    try:
                        response_str = await asyncio.wait_for(
                            websocket.recv(), timeout=200
                        )
                    except asyncio.TimeoutError:
                        print("Timeout on websocket.recv()! Will proceed to saving")
                        break
                    except websockets.exceptions.ConnectionClosed as e:
                        print(f"WebSocket connection closed: {e}")
                        break

                    # it seems websocket.recv() is annotated with return type Data, but decoding from it to str causes an error
                    # parse the JSON string received from the server
                    message = jsons.loads(response_str, cls=Message)  # type: ignore

                    print(
                        f"\n========== Received from bot for {message.recipient} : {response_str}\n"
                    )

                    if message.message_type == SessionCompleted.message_type:
                        print("Session marked completed")
                        return self.datum_id

                    # relay the message to the appropriate user
                    user = message.recipient
                    assert isinstance(user, Person)
                    # print(f"\n== Relaying message to {user}\n")

                    if message.is_content_type:
                        # skip the messages that are not content type (e.g. RequestAccepted)

                        if user.person_id not in self.participant_simulators:
                            error_msg = Message(
                                sender=self.main_user,
                                recipient=self.bot,
                                content=f"Error: no such user: {user}",
                                message_type="chat",
                            )
                            error_str = jsons.dumps(error_msg)
                            print(f"==== Sending to bot: {error_str}")
                            await websocket.send(error_str)
                            continue

                        user_simulator = self.participant_simulators[user.person_id]
                        response, send_message = await user_simulator.respond(message)

                        if send_message:
                            assert response is not None
                            # convert the response to a JSON string
                            # TODO: allow send_message to be '[complete]'; if so, then exit the loop (and send save)
                            response_str = jsons.dumps(response)
                            # send the response to the server
                            print(f"==== Sending to bot: {response_str}")
                            await websocket.send(response_str)
                        else:
                            print("==== No message sent to bot")
            except KeyboardInterrupt:
                print("Process interrupted by user! Will proceed to saving")
            except Exception as e:
                print(f"Error: {e}")
            finally:
                # We save here while the websocket is still open, because the data is cleaned up when ws closes
                print("Saving the session [finally block]")
                await self.save(save_folder)

    async def save(self, folder_path: str = "logs/"):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                demo_settings.get_save_url_with_custom_folder(
                    folder_path, datum_id=self.datum_id
                )
            )
            # Handle the response as needed
            if response.status_code == 200:
                print("Save endpoint called successfully")
                print("Saved to ", response.text)
            else:
                print(
                    f"Failed to call save endpoint. Status code: {response.status_code}"
                )
                print(response.text)


if __name__ == "__main__":
    config_name = sys.argv[1]  # experiment config json file
    save_folder = sys.argv[2]  # folder to save the outputs
    assert os.path.exists(config_name), f"Config file {config_name} not found"
    with open(config_name) as f:
        config_json = json.load(f)
        exp_config = ExpSimulHitlConfig.sim_config_builder(**config_json)

    dialog_manager = DialogManager(exp_config=exp_config)

    # for llm-powered simulation mode: please use carefully; can lead to lot of requests

    try:
        # run the session (and attempt save regardless of outcome)
        with time_limit(1250):
            asyncio.run(dialog_manager.run(save_folder))

    except Exception as e:
        print(f"[experiment_with_hitl_simulation] Error: {e}")
        raise e


# python src/experimentation/experiment_with_hitl_or_simulation.py workspace/sample_run/sample_spider_exp_config.json workspace/sample_run/saved_output
# python src/experimentation/experiment_with_hitl_or_simulation.py workspace/sample_run/sample_two_spider_exp_config.json workspace/sample_run/saved_output
