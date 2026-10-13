from .base import ParkingProvider, ProviderFetchResult
from .ghent import GhentParkingProvider
from .helsinki import HelsinkiParkingProvider
from .hong_kong import HongKongParkingProvider
from .netherlands_rdw import NetherlandsRdwProvider
from .parkapi import ParkApiProvider
from .parkendd import ParkenDdProvider
from .singapore import SingaporeHdbProvider

PROVIDERS: tuple[ParkingProvider, ...] = (
    ParkenDdProvider(),
    HelsinkiParkingProvider(),
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
