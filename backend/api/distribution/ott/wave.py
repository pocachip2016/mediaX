from .base import OttItem, OttSource


class WaveTopSource(OttSource):
    channel = "ott_wave"

    def fetch_top(self, limit: int = 20) -> list[OttItem]:
        # TODO: Wave 공식 Top 차트 데이터 소스 확정 후 구현
        return []
