from enum import Enum

from async_collab.llm.llm_client import LLMClient

class LLMModelName(Enum):
    dev_gpt_4_turbo = "dev-gpt-4-turbo"
    dev_gpt_35_turbo = "dev-gpt-35-turbo"
    dev_gpt_4_turbo_chat_completions = "dev-gpt-4-turbo-chat-completions"
    dev_gpt_4o_2024_05_13 = "dev-gpt-4o-2024-05-13"
    dev_phi3_medium_128k_instruct = "dev-phi-3-medium-128k-instruct"
    dev_gpt_4o_2024_05_13_chat_completions = "dev-gpt-4o-2024-05-13-chat-completions"
    o3_mini = "dev-gpt-o3-mini"
    o4_mini = "dev-gpt-o4-mini-2025-04-16"
    gpt_5_reasoning = "dev-gpt-5-reasoning"
    qwen_3_32b = "dev-qwen-3-32b"



class MyLLMClient(LLMClient):

    default_model: str

    def __init__(self, default_model: str = "dev-gpt-4-turbo"):
        self.default_model = default_model


    def send_request(self, request, model) -> dict:
        # TODO: add your client code

        print(f"[MyLLMClient] send_request: model = {model}")

        # return response.json()
        return {}

    def get_response_str(
        self,
        user_prompt: str,
        temperature: float = 0,
        max_tokens: int = 2800,
        top_p: float = 0.95,
        system_instruction: str = "",
        stop: str | None = None,
        model: str | None = None,
    ) -> str | None:
        if model is None:
            model = self.default_model
        if len(system_instruction) > 0:
            user_prompt = f"{system_instruction}\n{user_prompt}"

        # TODO -- fill you LLM API access code here
        # The function should return the response string

        # request_data = {
        #     "prompt": user_prompt,
        #     "max_tokens": max_tokens,
        #     "temperature": temperature,
        #     "top_p": top_p,
        #     "n": 1,
        #     "stream": False,
        #     "logprobs": None,
        #     "stop": stop,
        # }
        # response = self.send_request(request_data, model=model)
        # if response is None or len(response) == 0 or len(response["choices"]) == 0:
        #     print("[MyLLMClient] get_response_str: response is None")
        #     return None
        # print("[MyLLMClient] get_response_str: returning response")
        # return response["choices"][0]["text"]


llm_client: LLMClient | None = None


def get_llm_client(
    default_model: str = str(LLMModelName.dev_gpt_4_turbo.value),
) -> LLMClient:
    global llm_client
    if llm_client is None or llm_client.default_model != default_model:
        llm_client = MyLLMClient(default_model=default_model)
    return llm_client
