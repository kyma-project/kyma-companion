from routers.common import ReadynessModel


class Readyness:
    def is_hana_ready(self) -> bool:
        return True

    def is_redis_ready(self) -> bool:
        return True

    def are_llms_ready(self) -> bool:
        return True

    def get_llms_states(self) -> dict[str, bool]:
        return {"llm1": True, "llm2": True}

    def get_dto(self) -> ReadynessModel:
        return ReadynessModel(
            is_redis_ready=self.is_redis_ready(),
            is_hana_ready=self.is_hana_ready(),
            llms=self.get_llms_states(),
        )
