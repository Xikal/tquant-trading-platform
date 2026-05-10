__all__ = ["MLSignalService"]


def __getattr__(name: str):
    if name == "MLSignalService":
        from app.services.ml_signal.service import MLSignalService

        return MLSignalService
    raise AttributeError(name)
