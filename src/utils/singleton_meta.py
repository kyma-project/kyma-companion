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
