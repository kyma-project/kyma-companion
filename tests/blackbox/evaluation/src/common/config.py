import os


class Config:
    """
    Config represent the test configurations.
    """

    test_data_path: str
    namespace_scoped_test_data_path: str
    companion_api_url: str
    companion_token: str
    test_cluster_url: str
    test_cluster_ca_data: str
    test_cluster_auth_token: str
    aicore_deployment_id_gpt4: str
    aicore_configuration_id_gpt4: str
    model_name: str
    model_temperature: int

    def init(self) -> None:
        self.test_data_path = os.environ.get("TEST_DATA_PATH")
        if self.test_data_path is None or self.test_data_path == "":
            raise ValueError("ERROR: Env TEST_DATA_PATH is missing")
        self.namespace_scoped_test_data_path = (
            f"{self.test_data_path}/problems/namespace-scoped"
        )

        self.companion_api_url = os.environ.get("COMPANION_API_URL")
        if self.companion_api_url is None or self.companion_api_url == "":
            raise ValueError("ERROR: Env COMPANION_API_URL is missing")

        self.companion_token = os.environ.get("COMPANION_TOKEN")
        if self.companion_token is None or self.companion_token == "":
            raise ValueError("ERROR: Env COMPANION_TOKEN is missing")

        self.test_cluster_url = os.environ.get("TEST_CLUSTER_URL")
        if self.test_cluster_url is None or self.test_cluster_url == "":
            raise ValueError("ERROR: Env TEST_CLUSTER_URL is missing")

        self.test_cluster_ca_data = os.environ.get("TEST_CLUSTER_CA_DATA")
        if self.test_cluster_ca_data is None or self.test_cluster_ca_data == "":
            raise ValueError("ERROR: Env TEST_CLUSTER_CA_DATA is missing")

        self.test_cluster_auth_token = os.environ.get("TEST_CLUSTER_AUTH_TOKEN")
        if self.test_cluster_auth_token is None or self.test_cluster_auth_token == "":
            raise ValueError("ERROR: Env TEST_CLUSTER_AUTH_TOKEN is missing")

        self.aicore_deployment_id_gpt4 = os.environ.get("AICORE_DEPLOYMENT_ID_GPT4")
        if (
            self.aicore_deployment_id_gpt4 is None
            or self.aicore_deployment_id_gpt4 == ""
        ):
            raise ValueError("ERROR: Env AICORE_DEPLOYMENT_ID_GPT4 is missing")

        self.aicore_configuration_id_gpt4 = os.environ.get(
            "AICORE_CONFIGURATION_ID_GPT4"
        )
        if (
            self.aicore_configuration_id_gpt4 is None
            or self.aicore_configuration_id_gpt4 == ""
        ):
            raise ValueError("ERROR: Env AICORE_CONFIGURATION_ID_GPT4 is missing")

        self.model_name = os.getenv("MODEL_NAME", "gpt4.o")
        self.model_temperature = 0
