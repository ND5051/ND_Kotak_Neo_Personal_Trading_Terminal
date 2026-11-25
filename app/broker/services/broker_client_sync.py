from typing import Any, Optional

from app.broker.adapters.kotak_adapter import kotak_adapter
from app.broker.adapters.kotak_order_adapter import kotak_order_adapter
from app.broker.services.websocket_supervisor import ws_supervisor
from app.portfolio.services.portfolio_service import portfolio_service


def sync_shared_broker_client(client: Optional[Any]) -> None:
    """
    Propagate the single authenticated NeoAPI client instance across:
    - Broker Auth Adapter (kotak_adapter)
    - Order Execution Adapter (kotak_order_adapter)
    - Portfolio Services (portfolio_service.adapter)
    - Streaming Services (ws_supervisor.adapter)
    """
    kotak_adapter.client = client
    kotak_order_adapter.client = client
    ws_supervisor.adapter.client = client
    if portfolio_service.adapter is not kotak_adapter:
        portfolio_service.adapter.client = client
    try:
        from app.option_chain.services.option_chain_service import option_chain_service
        option_chain_service._neo_client = client
    except Exception:
        pass

