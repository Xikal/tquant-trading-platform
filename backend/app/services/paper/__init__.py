from importlib import import_module

__all__ = [
    "OrderSide",
    "OrderType",
    "PaperAccountService",
    "PaperArchiveService",
    "PaperMatchingEngine",
    "PaperOrderService",
    "PaperAutoTrader",
    "PaperPerformanceService",
    "PaperPositionService",
    "PaperRiskControlService",
    "get_auto_trader",
    "start_auto_trader",
    "stop_auto_trader",
]

_EXPORTS = {
    "OrderSide": ("app.services.paper.matching", "OrderSide"),
    "OrderType": ("app.services.paper.matching", "OrderType"),
    "PaperAccountService": ("app.services.paper.account", "PaperAccountService"),
    "PaperArchiveService": ("app.services.paper.archive", "PaperArchiveService"),
    "PaperMatchingEngine": ("app.services.paper.matching", "PaperMatchingEngine"),
    "PaperOrderService": ("app.services.paper.order", "PaperOrderService"),
    "PaperAutoTrader": ("app.services.paper.scheduler", "PaperAutoTrader"),
    "PaperPerformanceService": ("app.services.paper.performance", "PaperPerformanceService"),
    "PaperPositionService": ("app.services.paper.position", "PaperPositionService"),
    "PaperRiskControlService": ("app.services.paper.risk_control", "PaperRiskControlService"),
    "get_auto_trader": ("app.services.paper.scheduler", "get_auto_trader"),
    "start_auto_trader": ("app.services.paper.scheduler", "start_auto_trader"),
    "stop_auto_trader": ("app.services.paper.scheduler", "stop_auto_trader"),
}


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, attr_name = _EXPORTS[name]
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
