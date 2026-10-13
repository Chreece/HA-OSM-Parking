from .base import ParkingProvider, ProviderFetchResult
from .hong_kong import HongKongParkingProvider
from .parkapi import ParkApiProvider
from .singapore import SingaporeHdbProvider

PROVIDERS: tuple[ParkingProvider, ...] = (
    ParkApiProvider(),
    HongKongParkingProvider(),
    SingaporeHdbProvider(),
)

__all__ = [
    "PROVIDERS",
    "ParkingProvider",
    "ProviderFetchResult",
]
