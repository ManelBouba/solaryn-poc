import pandas as pd
import pytest

from src.data_fetchers import (
    _parse_power_hourly_json,
    nasa_hourly_to_site_summary,
    pvlib_azimuth_to_pvgis_aspect,
)


def test_parse_hourly_power_json():
    payload = {
        "properties": {
            "parameter": {
                "ALLSKY_SFC_SW_DWN": {"2024010100": 0, "2024010112": 800},
                "T2M": {"2024010100": 20, "2024010112": 30},
                "RH2M": {"2024010100": 70, "2024010112": 35},
                "WS10M": {"2024010100": 2.0, "2024010112": 4.0},
                "PRECTOTCORR": {"2024010100": 0, "2024010112": 0},
                "PS": {"2024010100": 101.0, "2024010112": 101.0},
            }
        }
    }
    df = _parse_power_hourly_json(payload)
    assert len(df) == 2
    assert str(df["time_utc"].dt.tz) == "UTC"
    assert df.loc[1, "ALLSKY_SFC_SW_DWN"] == 800


def test_pvlib_azimuth_to_pvgis_aspect_official_conventions():
    expected = {
        180.0: 0.0,   # south
        90.0: -90.0,  # east
        270.0: 90.0,  # west
        0.0: -180.0,  # north
        360.0: -180.0,
    }
    for pvlib_azimuth, pvgis_aspect in expected.items():
        assert pvlib_azimuth_to_pvgis_aspect(pvlib_azimuth) == pytest.approx(pvgis_aspect)


def _short_hourly():
    return pd.DataFrame({
        "time_utc": pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC"),
        "ALLSKY_SFC_SW_DWN": [500.0, 500.0],
        "ALLSKY_SFC_SW_DNI": [600.0, 600.0],
        "ALLSKY_SFC_SW_DIFF": [100.0, 100.0],
        "T2M": [20.0, 22.0], "RH2M": [50.0, 60.0], "WS10M": [3.0, 3.0],
        "PRECTOTCORR": [0.0, 0.0], "PS": [101.0, 101.0],
    })


def test_partial_period_is_rejected_for_annual_analysis():
    with pytest.raises(ValueError, match="near-complete reference year"):
        nasa_hourly_to_site_summary(_short_hourly(), 50.0, 4.0)


def test_partial_period_can_be_summarized_only_when_explicitly_requested():
    site = nasa_hourly_to_site_summary(_short_hourly(), 50.0, 4.0, require_full_year=False).iloc[0]
    assert pd.isna(site["ghi_kwh_m2_year"])
    assert site["avg_temp_c"] == 21.0
    assert site["is_full_reference_year"] == False
