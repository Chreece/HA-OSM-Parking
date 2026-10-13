from .base import ParkingProvider, ProviderFetchResult
from .hong_kong import HongKongParkingProvider
from .parkapi import ParkApiProvider

PROVIDERS: tuple[ParkingProvider, ...] = (
    ParkApiProvider(),
    HongKongParkingProvider(),
)

__all__ = [
    "PROVIDERS",
    "ParkingProvider",
    "ProviderFetchResult",
]
