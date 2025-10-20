from __future__ import annotations

from .bazaar import BazaarIAPProvider
from .iran_gw import IranianGatewayProvider

PROVIDER_REGISTRY = {
    IranianGatewayProvider.code: IranianGatewayProvider,
    BazaarIAPProvider.code: BazaarIAPProvider,
}


def get_provider_class(code: str):
    return PROVIDER_REGISTRY.get(code)

