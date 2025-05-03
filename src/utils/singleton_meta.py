class SingletonMeta(type):
    """Singleton metaclass."""

    _instances: dict[type, object] = {}

    def __call__(cls, *args, **kwargs):  # noqa A002
        """
        Possible changes to the value of the `__init__` argument do not affect
        the returned instance.
        """
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]

    @classmethod
    def reset_instance(cls, target_cls: type) -> None:
        """
        Remove the singleton instance of the specified class, if it exists.

        Args:
            target_cls (type): The class whose singleton instance should be removed.
        """
        if target_cls in cls._instances:
            del cls._instances[target_cls]
