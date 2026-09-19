from core.schemas.common import severity_band_for


def test_boundaries():
    assert severity_band_for(0) == "good"
    assert severity_band_for(30) == "good"
    assert severity_band_for(30.1) == "satisfactory"
    assert severity_band_for(60) == "satisfactory"
    assert severity_band_for(60.1) == "moderate"
    assert severity_band_for(90) == "moderate"
    assert severity_band_for(90.1) == "poor"
    assert severity_band_for(120) == "poor"
    assert severity_band_for(120.1) == "very_poor"
    assert severity_band_for(250) == "very_poor"
    assert severity_band_for(250.1) == "severe"
    assert severity_band_for(1000) == "severe"
