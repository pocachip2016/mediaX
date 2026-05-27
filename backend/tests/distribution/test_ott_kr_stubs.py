"""distribution-step2.4 — Wave/Tving stub 어댑터 테스트"""
from api.distribution.ott.tving import TvingTopSource
from api.distribution.ott.wave import WaveTopSource


def test_wave_instantiable_and_returns_empty():
    source = WaveTopSource()
    assert source.fetch_top() == []
    assert source.channel == "ott_wave"


def test_tving_instantiable_and_returns_empty():
    source = TvingTopSource()
    assert source.fetch_top() == []
    assert source.channel == "ott_tving"
