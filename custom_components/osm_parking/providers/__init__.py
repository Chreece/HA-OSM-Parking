from .base import ParkingProvider, ProviderFetchResult
from .ghent import GhentParkingProvider
from .hong_kong import HongKongParkingProvider
from .netherlands_rdw import NetherlandsRdwProvider
from .parkapi import ParkApiProvider
from .singapore import SingaporeHdbProvider

PROVIDERS: tuple[ParkingProvider, ...] = (
    NetherlandsRdwProvider(),
    GhentParkingProvider(),
    ParkApiProvider(),
    HongKongParkingProvider(),
    SingaporeHdbProvider(),
)

__all__ = [
    "PROVIDERS",
    "ParkingProvider",
    "ProviderFetchResult",
]
