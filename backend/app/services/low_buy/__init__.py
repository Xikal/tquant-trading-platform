from app.services.low_buy.shared import BoardCandidate, PLAYBOOKS

__all__ = ["BoardCandidate", "LowBuyScreenerService", "PLAYBOOKS"]


def __getattr__(name: str):
    if name == "LowBuyScreenerService":
        from app.services.low_buy.service import LowBuyScreenerService

        return LowBuyScreenerService
    raise AttributeError(name)
