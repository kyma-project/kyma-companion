from src.common.utils import get_env


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
    iterations: int

    def init(self) -> None:
        self.test_data_path = get_env("TEST_DATA_PATH")
        self.namespace_scoped_test_data_path = (
            f"{self.test_data_path}/evaluation/namespace-scoped"
        )

        self.companion_api_url = get_env("COMPANION_API_URL")
        self.companion_token = get_env("COMPANION_TOKEN")
        self.test_cluster_url = get_env("TEST_CLUSTER_URL")
        self.test_cluster_ca_data = get_env("TEST_CLUSTER_CA_DATA")
        self.test_cluster_auth_token = get_env("TEST_CLUSTER_AUTH_TOKEN")
        self.aicore_deployment_id_gpt4 = get_env("AICORE_DEPLOYMENT_ID_GPT4")
        self.aicore_configuration_id_gpt4 = get_env("AICORE_CONFIGURATION_ID_GPT4")
        self.model_name = get_env("MODEL_NAME", False, "gpt4.o")
        self.model_temperature = 0
        self.iterations = 3
