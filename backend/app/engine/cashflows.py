from backend.app.domain.enums import CashflowType, Frequency
from backend.app.domain.schemas import BacktestRequest


def cashflow_due(index_position: int, request: BacktestRequest) -> bool:
    if not request.cashflow.enabled or index_position == 0:
        return False
    if request.cashflow.frequency == Frequency.monthly:
        return True
    if request.cashflow.frequency == Frequency.quarterly:
        return index_position % 3 == 0
    if request.cashflow.frequency == Frequency.annual:
        return index_position % 12 == 0
    return False


def signed_cashflow_amount(request: BacktestRequest) -> float:
    if not request.cashflow.enabled:
        return 0.0
    if request.cashflow.type == CashflowType.withdrawal:
        return -request.cashflow.amount
    return request.cashflow.amount
