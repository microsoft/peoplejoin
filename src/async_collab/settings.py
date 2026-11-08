from dataclasses import dataclass


@dataclass(frozen=True)
class DemoSettings:
    backend_port: int = 8000
    frontend_port: int = 3000  # TODO: use this port in the frontend
    backend_host: str = "localhost"
    clear_endpoint: str = "/clear"

    @property
    def backend_url(self) -> str:
        return f"http://{self.backend_host}:{self.backend_port}"

    @property
    def clear_url(self) -> str:
        return f"{self.backend_url}{self.clear_endpoint}"

    @property
    def connect_url(self) -> str:  # "ws://localhost:8000/ws"
        return f"ws://{self.backend_host}:{self.backend_port}/ws"

    @property
    def save_url(self) -> str:
        return f"{self.backend_url}/save"

    def get_connect_url(self, user_id: str) -> str:
        return f"ws://{self.backend_host}:{self.backend_port}/ws/{user_id}"

    def get_clear_url(self) -> str:
        return f"{self.clear_url}"

    def get_init_url(self) -> str:
        return f"{self.backend_url}/init"


demo_settings = DemoSettings()
