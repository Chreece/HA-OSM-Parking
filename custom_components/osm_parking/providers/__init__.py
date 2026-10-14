"""Load optional providers independently; broken modules cannot prevent setup."""
from importlib import import_module
import logging
from .base import ParkingProvider, ProviderFetchResult
_LOGGER=logging.getLogger(__name__)
PROVIDER_SPECS=(('paris', 'ParisBnlsProvider'), ('zaragoza', 'ZaragozaParkingProvider'), ('singapore_ura', 'SingaporeUraProvider'), ('athens_zones', 'AthensParkingZonesProvider'), ('ispark', 'IstanbulIsparkProvider'), ('izmir', 'IzmirIzumProvider'), ('lille', 'LilleParkingProvider'), ('grenoble', 'GrenobleParkingProvider'), ('lyon', 'LyonParkingProvider'), ('nantes', 'NantesPublicParkingProvider'), ('nantes', 'NantesParkAndRideProvider'), ('strasbourg', 'StrasbourgParkingProvider'), ('montpellier', 'MontpellierParkingProvider'), ('malaga', 'MalagaParkingProvider'), ('luxembourg_city', 'LuxembourgCityParkingProvider'), ('luxembourg_cfl', 'CflParkAndRideProvider'), ('basel_stadt', 'BaselStadtParkingProvider'), ('zurich_pls', 'ZurichPlsProvider'), ('swiss', 'SwissParkingProvider'), ('st_gallen', 'StGallenParkingProvider'), ('madrid', 'MadridParkingProvider'), ('melbourne', 'MelbourneParkingProvider'), ('brussels', 'BrusselsParkingProvider'), ('dublin', 'DublinParkingProvider'), ('fintraffic', 'FintrafficLiipiProvider'), ('tfl', 'TflCarParkProvider'), ('tdx', 'TaiwanTdxParkingProvider'), ('golemio', 'GolemioParkingProvider'), ('tfnsw', 'TfNswParkingProvider'), ('parkendd', 'ParkenDdProvider'), ('helsinki', 'HelsinkiParkingProvider'), ('netherlands_rdw', 'NetherlandsRdwProvider'), ('ghent', 'GhentParkingProvider'), ('parkapi', 'ParkApiProvider'), ('hong_kong', 'HongKongParkingProvider'), ('singapore', 'SingaporeHdbProvider'), ('toulouse', 'ToulouseParkingProvider'))


def load_providers(specs=PROVIDER_SPECS):
    providers,errors=[],{}
    for module,class_name in specs:
        try:
            factory=getattr(import_module('.'+module,__name__),class_name)
            providers.append(factory())
        except Exception as exc:
            errors[module]=type(exc).__name__
            _LOGGER.warning('Parking provider %s unavailable (%s)',module,type(exc).__name__)
    return tuple(providers),errors


PROVIDERS,PROVIDER_LOAD_ERRORS=load_providers()
__all__=['PROVIDERS','PROVIDER_LOAD_ERRORS','ParkingProvider','ProviderFetchResult']
