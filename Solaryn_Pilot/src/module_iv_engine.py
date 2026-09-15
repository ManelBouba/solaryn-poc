from __future__ import annotations

from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

from src.evidence_policy import (
    electrical_model_policy,
    spectral_evidence_policy,
    thermal_evidence_policy,
)
from src.iec61853_engine import (
    interpolate_iec61853_pmax,
    read_iec61853_matrix,
    validate_iec61853_matrix,
)

try:
    import pvlib
except ImportError:
    pvlib = None


REQUIRED_MODULE_FIELDS = [
    "module_id", "technology_id", "manufacturer", "model", "cec_celltype",
    "pmax_w", "vmp_v", "imp_a", "voc_v", "isc_a",
    "alpha_isc_pct_c", "beta_voc_pct_c", "gamma_pmax_pct_c",
    "cells_in_series", "module_area_m2", "module_efficiency_pct",
    "thermal_construction", "first_year_retention_pct",
    "annual_warranty_degradation_pct_year", "warranty_years",
]


def require_pvlib() -> None:
    if pvlib is None:
        raise ImportError(
            "EPC physics mode requires pvlib. Datasheet CEC fitting also requires NREL-PySAM. "
            "Install project requirements before running live hourly simulations."
        )


def validate_module_candidates(df: pd.DataFrame) -> None:
    """Reject impossible/incomplete candidate records before nonlinear modeling.

    This validation is intentionally strict. Solaryn must fail closed rather than
    compensate for missing or inconsistent module data with technology heuristics.
    """
    missing = [c for c in REQUIRED_MODULE_FIELDS if c not in df.columns]
    if missing:
        raise ValueError(f"Module candidate table is missing required columns: {missing}")
    if df.empty:
        raise ValueError("At least one module candidate is required.")

    if df["module_id"].astype(str).duplicated().any():
        raise ValueError("module_id must be unique.")
    for field in ["module_id", "manufacturer", "model"]:
        if df[field].isna().any() or df[field].astype(str).str.strip().eq("").any():
            raise ValueError(f"{field} cannot be blank.")
    numeric_positive = [
        "pmax_w", "vmp_v", "imp_a", "voc_v", "isc_a",
        "cells_in_series", "module_area_m2", "module_efficiency_pct",
    ]
    for col in numeric_positive:
        vals = pd.to_numeric(df[col], errors="coerce")
        if not np.isfinite(vals).all() or (vals <= 0).any():
            raise ValueError(f"{col} must contain positive numeric values for every selected module.")

    r1 = pd.to_numeric(df["first_year_retention_pct"], errors="coerce")
    if r1.isna().any() or ((r1 <= 0) | (r1 > 100)).any():
        raise ValueError("first_year_retention_pct must be in (0,100].")
    d = pd.to_numeric(df["annual_warranty_degradation_pct_year"], errors="coerce")
    if not np.isfinite(d).all() or (d < 0).any() or (d >= 100).any():
        raise ValueError("annual_warranty_degradation_pct_year cannot be negative.")

    for _, row in df.iterrows():
        for key in ["alpha_isc_pct_c", "beta_voc_pct_c", "gamma_pmax_pct_c", "warranty_years"]:
            if not np.isfinite(float(row[key])):
                raise ValueError(f"{key} must be finite.")
        wy = float(row["warranty_years"])
        if wy != int(wy) or not 1 <= wy <= 100:
            raise ValueError("Warranty years must be an integer in [1, 100].")
        calculated_eff = float(row["pmax_w"]) / (10 * float(row["module_area_m2"]))
        if abs(calculated_eff - float(row["module_efficiency_pct"])) > 0.5:
            raise ValueError("Area, power and efficiency are inconsistent.")
        pmax = float(row["pmax_w"])
        vmp = float(row["vmp_v"])
        imp = float(row["imp_a"])
        voc = float(row["voc_v"])
        isc = float(row["isc_a"])
        if not (0 < vmp < voc):
            raise ValueError(f"{row['module_id']}: require 0 < Vmp < Voc.")
        if not (0 < imp < isc):
            raise ValueError(f"{row['module_id']}: require 0 < Imp < Isc.")
        residual = abs(vmp * imp - pmax) / max(pmax, 1e-9)
        if residual > 0.02:
            raise ValueError(
                f"{row['module_id']}: Vmp×Imp differs from Pmax by {residual:.1%}; "
                "verify the datasheet row/units before fitting the IV model."
            )
        gamma = float(row["gamma_pmax_pct_c"])
        beta = float(row["beta_voc_pct_c"])
        if gamma > 0:
            raise ValueError(f"{row['module_id']}: gamma_pmax_pct_c should normally be negative; verify the datasheet.")
        if beta > 0:
            raise ValueError(f"{row['module_id']}: beta_voc_pct_c should normally be negative; verify the datasheet.")
        cells = float(row["cells_in_series"])
        if abs(cells - round(cells)) > 1e-9:
            raise ValueError(f"{row['module_id']}: cells_in_series must be an integer electrical series count.")

        # Bifaciality is optional, but when supplied it is a physical module property
        # and must be validated instead of silently clipped. Values above 1 are
        # possible in principle for unusual definitions, so the product contract uses
        # a conservative 0..1.2 sanity domain and requires provenance for any
        # positive decision input. Annual bifacial *gain* is never read from this
        # field; it is calculated from rear irradiance geometry.
        if "bifaciality_factor" in df.columns:
            raw_bif = row.get("bifaciality_factor", 0.0)
            bif = 0.0 if pd.isna(raw_bif) or str(raw_bif).strip() == "" else float(raw_bif)
            if not np.isfinite(bif) or bif < 0.0 or bif > 1.2:
                raise ValueError(f"{row['module_id']}: bifaciality_factor must be finite and in [0, 1.2].")
            if bif > 0.0 and "bifaciality_source" in df.columns:
                source = str(row.get("bifaciality_source", "") or "").strip()
                if not source or source.lower() == "nan":
                    raise ValueError(f"{row['module_id']}: positive bifaciality_factor requires bifaciality_source provenance.")

        if "bifaciality_tolerance_pct_points" in df.columns:
            raw_tol = row.get("bifaciality_tolerance_pct_points", 0.0)
            tol = 0.0 if pd.isna(raw_tol) or str(raw_tol).strip() == "" else float(raw_tol)
            if not np.isfinite(tol) or tol < 0.0 or tol > 50.0:
                raise ValueError(f"{row['module_id']}: bifaciality_tolerance_pct_points must be finite and in [0, 50].")


def _spectral_module_type(row: pd.Series) -> str | None:
    cec = str(row.get("cec_celltype", "")).strip().lower()
    mapping = {
        "monosi": "monosi",
        "multisi": "multisi",
        "polysi": "multisi",
        "cigs": "cigs",
        "cis": "cigs",
        "cdte": "cdte",
        "amorphous": "asi",
    }
    return mapping.get(cec)


def spectral_factor_for_module(
    weather: pd.DataFrame,
    row: pd.Series,
    *,
    strict: bool = False,
) -> pd.Series:
    """Return a technology-class spectral factor for sensitivity analysis.

    The pvlib First Solar model has a bounded atmospheric input domain. Because
    Solaryn treats this technology-class model as a *sensitivity* rather than
    primary decision evidence, unsupported daylight hours must not abort the
    broadband EPC simulation. In non-strict mode those hours receive a neutral
    factor of 1.0 (no spectral correction) and the coverage shortfall is exposed
    in ``Series.attrs`` for reporting.

    ``strict=True`` is reserved for a future decision-grade spectral path: any
    unsupported daylight hour then fails closed instead of being neutralized.
    """
    require_pvlib()
    index = weather.index
    neutral = pd.Series(1.0, index=index, dtype=float)

    module_type = _spectral_module_type(row)
    poa = pd.to_numeric(
        weather.get("poa_optical_w_m2", weather.get("poa_w_m2", pd.Series(0.0, index=index))),
        errors="coerce",
    ).fillna(0.0)
    daylight = poa > 20.0
    daylight_count = int(daylight.sum())

    def _attach_metadata(
        factor: pd.Series,
        *,
        status: str,
        invalid_mask: pd.Series | None = None,
        note: str = "",
    ) -> pd.Series:
        invalid = (
            invalid_mask.reindex(index, fill_value=False).astype(bool)
            if invalid_mask is not None
            else pd.Series(False, index=index, dtype=bool)
        )
        invalid_count = int((invalid & daylight).sum())
        invalid_pct = 100.0 * invalid_count / max(daylight_count, 1)
        factor.attrs.update({
            "spectral_proxy_status": status,
            "spectral_proxy_note": note,
            "spectral_proxy_invalid_daylight_hours": invalid_count,
            "spectral_proxy_invalid_daylight_fraction_pct": invalid_pct,
            "spectral_proxy_valid_daylight_fraction_pct": 100.0 - invalid_pct if daylight_count else 100.0,
            "spectral_proxy_fallback_policy": (
                "neutral_factor_1.0_no_spectral_correction_for_unsupported_hours"
                if invalid_count else "none"
            ),
            "spectral_proxy_invalid_daylight_mask": invalid,
        })
        return factor

    if module_type is None:
        return _attach_metadata(
            neutral,
            status="not_available_for_module_class",
            note="No supported pvlib First Solar technology-class proxy for this module class.",
        )

    required = {"airmass_absolute", "precipitable_water_cm"}
    missing = sorted(required.difference(weather.columns))
    if missing:
        if strict and daylight_count:
            raise ValueError(
                "Decision-grade spectral calculation requires atmospheric inputs: "
                + ", ".join(missing)
            )
        invalid = daylight.copy()
        return _attach_metadata(
            neutral,
            status="atmospheric_inputs_unavailable_neutralized",
            invalid_mask=invalid,
            note=(
                "Spectral sensitivity unavailable because required atmospheric inputs are missing; "
                "broadband simulation remains primary."
            ),
        )

    am = pd.to_numeric(weather["airmass_absolute"], errors="coerce")
    pw = pd.to_numeric(weather["precipitable_water_cm"], errors="coerce")

    # pvlib's current First Solar implementation clips very low PW/AM and high AM,
    # while PW > 8 cm becomes NaN. We still derive validity from the returned factor
    # so this remains compatible with future pvlib versions and missing input values.
    try:
        raw = pvlib.spectrum.spectral_factor_firstsolar(
            precipitable_water=pw,
            airmass_absolute=am,
            module_type=module_type,
        )
        factor = pd.Series(raw, index=index, dtype=float)
    except Exception as exc:
        if strict and daylight_count:
            raise ValueError(
                f"Decision-grade spectral proxy failed for {row['manufacturer']} {row['model']}: {exc}"
            ) from exc
        invalid = daylight.copy()
        return _attach_metadata(
            neutral,
            status="calculation_failed_neutralized",
            invalid_mask=invalid,
            note=f"Technology-class spectral sensitivity failed safely: {exc}",
        )

    invalid_daylight = daylight & (~np.isfinite(factor))
    if invalid_daylight.any() and strict:
        pct = 100.0 * float(invalid_daylight.sum()) / max(float(daylight_count), 1.0)
        raise ValueError(
            f"Spectral proxy is outside its valid input domain for {pct:.1f}% of daylight hours "
            f"for {row['manufacturer']} {row['model']}."
        )

    # IMPORTANT: 1.0 is not an invented spectral gain/loss. It means *no spectral
    # correction* for the unsupported sensitivity hours. The primary broadband
    # calculation is unchanged and remains the decision energy in the current engine.
    factor.loc[invalid_daylight] = 1.0
    factor.loc[~daylight] = 1.0

    status = "complete_validity" if not invalid_daylight.any() else "partial_validity_neutralized"
    note = (
        "All daylight hours were within the executable proxy domain."
        if not invalid_daylight.any()
        else (
            "Unsupported daylight hours were assigned factor 1.0 for the spectral sensitivity only; "
            "the primary broadband energy calculation was not altered."
        )
    )
    return _attach_metadata(
        factor,
        status=status,
        invalid_mask=invalid_daylight,
        note=note,
    )

def _candidate_bifaciality(row: pd.Series) -> float:
    raw = row.get("bifaciality_factor", 0.0)
    try:
        value = float(raw) if pd.notna(raw) else 0.0
    except (TypeError, ValueError):
        value = 0.0
    if value < 0.0 or value > 1.2:
        raise ValueError(f"{row.get('module_id','candidate')}: bifaciality_factor must be between 0 and 1.2.")
    return value


def candidate_plane_of_array(
    weather: pd.DataFrame,
    row: pd.Series,
    bifacial_config: dict | None = None,
) -> dict:
    """Return front/rear/effective POA for the candidate under one common geometry.

    When row geometry is disabled, the existing Perez-Driesse front-side POA is
    preserved and no rear-side gain is invented. When enabled, pvlib's validated
    infinite-sheds geometry is used for *every* candidate so row shading is common.
    Candidate bifaciality converts rear optical irradiance into front-equivalent
    electrical irradiance; the annual bifacial gain is therefore an output rather
    than a hard-coded technology bonus.
    """
    require_pvlib()
    cfg = dict(bifacial_config or {})
    enabled = bool(cfg.get("enabled", False))
    front_reference = pd.to_numeric(weather["poa_w_m2"], errors="coerce").fillna(0).clip(lower=0)
    front_default = pd.to_numeric(
        weather.get("poa_optical_w_m2", weather["poa_w_m2"]), errors="coerce"
    ).fillna(0).clip(lower=0)
    zeros = pd.Series(0.0, index=weather.index, dtype=float)
    bifaciality = _candidate_bifaciality(row)

    if not enabled:
        return {
            "front_reference_w_m2": front_reference,
            "front_optical_w_m2": front_default,
            "rear_optical_w_m2": zeros,
            "rear_equivalent_w_m2": zeros,
            "effective_electrical_poa_w_m2": front_default,
            "bifaciality_factor": bifaciality,
            "rear_irradiance_model_active": False,
            "poa_geometry_basis": "unshaded_single_plane_front_side_only",
            "rear_model_note": (
                "Candidate is bifacial but rear irradiance geometry was not enabled; no rear gain is included."
                if bifaciality > 0 else "Monofacial/front-side calculation."
            ),
        }

    gcr = float(cfg.get("gcr", 0.40))
    height = float(cfg.get("height_m", 1.5))
    pitch = float(cfg.get("pitch_m", 5.0))
    albedo = float(cfg.get("albedo", 0.20))
    rear_structure_loss_pct = float(cfg.get("rear_structure_loss_pct", 2.0))
    if not (0.02 <= gcr <= 0.95):
        raise ValueError("Array GCR must be between 0.02 and 0.95.")
    if height <= 0 or pitch <= 0:
        raise ValueError("Array row height and pitch must be positive.")
    if not (0.0 <= albedo <= 1.0):
        raise ValueError("Albedo must be between 0 and 1.")
    if not (0.0 <= rear_structure_loss_pct <= 50.0):
        raise ValueError("Rear structural/mismatch screening loss must be between 0 and 50%.")

    required = [
        "ghi_w_m2", "dhi_w_m2", "dni_w_m2", "solar_zenith_deg", "solar_azimuth_deg",
        "time_utc", "surface_tilt_deg", "surface_azimuth_deg",
    ]
    missing = [c for c in required if c not in weather.columns]
    if missing:
        raise ValueError(f"Bifacial row geometry requires weather fields: {missing}")

    tilt = float(pd.to_numeric(weather["surface_tilt_deg"], errors="coerce").dropna().iloc[0])
    azimuth = float(pd.to_numeric(weather["surface_azimuth_deg"], errors="coerce").dropna().iloc[0])
    if not (0.0 <= tilt <= 180.0) or not (0.0 <= azimuth < 360.0):
        raise ValueError("Surface tilt must be in [0,180] and azimuth in [0,360) degrees.")

    # Infinite-sheds defines GCR as row slant length / pitch and height as the
    # row center elevation. Reject geometry that would place the lower module edge
    # at or below ground; allowing it would create numerically valid but physically
    # impossible rear-view factors.
    row_slant_length = gcr * pitch
    lower_edge_height = height - 0.5 * row_slant_length * abs(np.sin(np.deg2rad(tilt)))
    if lower_edge_height <= 0.0:
        raise ValueError(
            "Array geometry is physically inconsistent: GCR×pitch and tilt place the lower module edge at/below ground. "
            "Increase center height or reduce row slant length/GCR."
        )
    times = pd.DatetimeIndex(pd.to_datetime(weather["time_utc"], utc=True))
    dni_extra = pd.Series(np.asarray(pvlib.irradiance.get_extra_radiation(times)), index=weather.index, dtype=float)
    zenith = pd.to_numeric(weather["solar_zenith_deg"], errors="coerce")
    solar_azimuth = pd.to_numeric(weather["solar_azimuth_deg"], errors="coerce")
    ghi = pd.to_numeric(weather["ghi_w_m2"], errors="coerce").fillna(0).clip(lower=0)
    dhi = pd.to_numeric(weather["dhi_w_m2"], errors="coerce").fillna(0).clip(lower=0)
    dni = pd.to_numeric(weather["dni_w_m2"], errors="coerce").fillna(0).clip(lower=0)

    aoi_front = pd.Series(
        pvlib.irradiance.aoi(tilt, azimuth, zenith, solar_azimuth), index=weather.index, dtype=float
    )
    back_tilt = 180.0 - tilt
    back_azimuth = (azimuth + 180.0) % 360.0
    aoi_back = pd.Series(
        pvlib.irradiance.aoi(back_tilt, back_azimuth, zenith, solar_azimuth), index=weather.index, dtype=float
    )
    iam_front = pd.Series(pvlib.iam.physical(aoi_front), index=weather.index, dtype=float).fillna(0).clip(0, 1.05)
    iam_back = pd.Series(pvlib.iam.physical(aoi_back), index=weather.index, dtype=float).fillna(0).clip(0, 1.05)

    irrad = pvlib.bifacial.infinite_sheds.get_irradiance(
        surface_tilt=tilt,
        surface_azimuth=azimuth,
        solar_zenith=zenith,
        solar_azimuth=solar_azimuth,
        gcr=gcr,
        height=height,
        pitch=pitch,
        ghi=ghi,
        dhi=dhi,
        dni=dni,
        albedo=albedo,
        model="haydavies",
        dni_extra=dni_extra,
        iam_front=iam_front,
        iam_back=iam_back,
        bifaciality=1.0,
        shade_factor=0.0,
        transmission_factor=0.0,
    )
    irrad = pd.DataFrame(irrad, index=weather.index)
    daylight = ghi > 20
    if not np.isfinite(irrad.loc[daylight].to_numpy(dtype=float)).all():
        raise ValueError("Row irradiance is missing/non-finite during daylight; calculation stopped.")

    front_diffuse_iam = pvlib.iam.marion_diffuse("physical", surface_tilt=tilt)
    back_diffuse_iam = pvlib.iam.marion_diffuse("physical", surface_tilt=back_tilt)
    front_optical = (
        pd.to_numeric(irrad["poa_front_direct"], errors="coerce").fillna(0)
        + pd.to_numeric(irrad["poa_front_sky_diffuse"], errors="coerce").fillna(0) * float(front_diffuse_iam["sky"])
        + pd.to_numeric(irrad["poa_front_ground_diffuse"], errors="coerce").fillna(0) * float(front_diffuse_iam["ground"])
    ).clip(lower=0)
    rear_optical = (
        pd.to_numeric(irrad["poa_back_direct"], errors="coerce").fillna(0)
        + pd.to_numeric(irrad["poa_back_sky_diffuse"], errors="coerce").fillna(0) * float(back_diffuse_iam["sky"])
        + pd.to_numeric(irrad["poa_back_ground_diffuse"], errors="coerce").fillna(0) * float(back_diffuse_iam["ground"])
    ).clip(lower=0)
    rear_delivery = max(0.0, 1.0 - rear_structure_loss_pct / 100.0)
    rear_equivalent = rear_optical * bifaciality * rear_delivery
    effective = (front_optical + rear_equivalent).clip(lower=0)

    return {
        "front_reference_w_m2": front_reference,
        "front_optical_w_m2": front_optical,
        "rear_optical_w_m2": rear_optical,
        "rear_equivalent_w_m2": rear_equivalent,
        "effective_electrical_poa_w_m2": effective,
        "bifaciality_factor": bifaciality,
        "rear_irradiance_model_active": True,
        "poa_geometry_basis": "pvlib_infinite_sheds_haydavies_common_row_geometry",
        "rear_model_note": (
            f"Rear optical irradiance × bifaciality {bifaciality:.3f} × "
            f"declared rear structural delivery {rear_delivery:.3f}. Front-side thermal model retained as a conservative screening boundary."
        ),
    }


def _sapm_temperature_parameters(row: pd.Series) -> dict:
    require_pvlib()
    construction = str(row.get("thermal_construction", "")).lower()
    if "glass_glass" in construction:
        key = "open_rack_glass_glass"
    else:
        key = "open_rack_glass_polymer"
    return pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS["sapm"][key]


def module_operating_temperatures(weather: pd.DataFrame, row: pd.Series, poa_global_w_m2: pd.Series | None = None) -> tuple[pd.Series, pd.Series]:
    """Return (module_temperature, cell_temperature) with explicit evidence policy.

    IEC 61853 G-T matrices are indexed by module/device temperature. The CEC
    single-diode model expects cell temperature. When module-specific Faiman U0/U1
    coefficients are supplied, pvlib/IEC usage does not distinguish between the two,
    so the same value is used for both. Otherwise SAPM module and cell temperatures
    are calculated separately using a transparent construction-class fallback.

    Thermal driving irradiance uses the common AOI-corrected POA (not the spectral
    sensitivity), matching the IEC energy-rating concept more closely and preventing a
    technology-class spectral proxy from changing module temperature.
    """
    require_pvlib()
    poa_source = poa_global_w_m2 if poa_global_w_m2 is not None else weather.get("poa_optical_w_m2", weather["poa_w_m2"])
    poa = pd.to_numeric(poa_source, errors="coerce").fillna(0).clip(lower=0)
    ta = pd.to_numeric(weather["temp_air_c"], errors="coerce").interpolate(limit_direction="both")
    wind = pd.to_numeric(weather["wind_speed_m_s"], errors="coerce").interpolate(limit_direction="both").clip(lower=0.1)
    thermal = thermal_evidence_policy(row)
    if thermal["thermal_evidence_level"] == "module_specific_u0_u1":
        t = pd.Series(
            pvlib.temperature.faiman(
                poa_global=poa, temp_air=ta, wind_speed=wind,
                u0=thermal["u0"], u1=thermal["u1"],
            ),
            index=weather.index, dtype=float,
        )
        return t, t.copy()

    params = _sapm_temperature_parameters(row)
    t_module = pd.Series(
        pvlib.temperature.sapm_module(
            poa_global=poa, temp_air=ta, wind_speed=wind,
            a=params["a"], b=params["b"],
        ),
        index=weather.index, dtype=float,
    )
    t_cell = pd.Series(
        pvlib.temperature.sapm_cell(
            poa_global=poa, temp_air=ta, wind_speed=wind, **params,
        ),
        index=weather.index, dtype=float,
    )
    return t_module, t_cell


def module_cell_temperature(weather: pd.DataFrame, row: pd.Series) -> pd.Series:
    """Backward-compatible helper returning cell temperature only."""
    return module_operating_temperatures(weather, row)[1]


def fit_cec_from_datasheet(row: pd.Series) -> Dict[str, float]:
    """Fit CEC single-diode parameters from sourced module-datasheet values."""
    require_pvlib()
    isc = float(row["isc_a"])
    voc = float(row["voc_v"])
    alpha_sc = isc * float(row["alpha_isc_pct_c"]) / 100.0
    beta_voc = voc * float(row["beta_voc_pct_c"]) / 100.0
    try:
        fitted = pvlib.ivtools.sdm.fit_cec_sam(
            celltype=str(row["cec_celltype"]),
            v_mp=float(row["vmp_v"]),
            i_mp=float(row["imp_a"]),
            v_oc=voc,
            i_sc=isc,
            alpha_sc=alpha_sc,
            beta_voc=beta_voc,
            gamma_pmp=float(row["gamma_pmax_pct_c"]),
            cells_in_series=int(row["cells_in_series"]),
            temp_ref=25,
        )
    except ImportError as exc:
        raise ImportError(
            "CEC datasheet fitting requires NREL-PySAM in addition to pvlib. Run `pip install -r requirements.txt`."
        ) from exc
    except RuntimeError as exc:
        raise RuntimeError(
            f"CEC parameter extraction failed for {row['manufacturer']} {row['model']}. "
            "Do not substitute invented diode parameters; verify datasheet inputs/cell count."
        ) from exc
    names = ["I_L_ref", "I_o_ref", "R_s", "R_sh_ref", "a_ref", "Adjust"]
    out = dict(zip(names, map(float, fitted)))
    out["alpha_sc_A_C"] = alpha_sc
    out["beta_voc_V_C"] = beta_voc
    return out


def _pmp_from_cec(effective_irradiance: pd.Series, temp_cell_c: pd.Series, fit: Dict[str, float]) -> pd.Series:
    """Return CEC-SDM maximum power while avoiding degenerate night-time solves.

    Exact-zero irradiance is physically zero output and does not need a nonlinear IV
    solve.  Solving only finite, positive-irradiance hours avoids numerical root-finder
    warnings without changing daylight physics or annual energy.
    """
    require_pvlib()
    ee = pd.to_numeric(effective_irradiance, errors="coerce")
    tc = pd.to_numeric(temp_cell_c, errors="coerce")
    out = pd.Series(0.0, index=effective_irradiance.index, dtype=float)
    valid = np.isfinite(ee) & np.isfinite(tc) & (ee > 0.0)
    if not bool(valid.any()):
        return out

    ee_v = ee.loc[valid]
    tc_v = tc.loc[valid]
    photocurrent, saturation_current, resistance_series, resistance_shunt, nNsVth = pvlib.pvsystem.calcparams_cec(
        effective_irradiance=ee_v,
        temp_cell=tc_v,
        alpha_sc=fit["alpha_sc_A_C"],
        a_ref=fit["a_ref"],
        I_L_ref=fit["I_L_ref"],
        I_o_ref=fit["I_o_ref"],
        R_sh_ref=fit["R_sh_ref"],
        R_s=fit["R_s"],
        Adjust=fit["Adjust"],
    )
    sd = pvlib.pvsystem.singlediode(
        photocurrent=photocurrent,
        saturation_current=saturation_current,
        resistance_series=resistance_series,
        resistance_shunt=resistance_shunt,
        nNsVth=nNsVth,
        method="lambertw",
    )
    if isinstance(sd, pd.DataFrame):
        vals = pd.to_numeric(sd["p_mp"], errors="coerce").clip(lower=0.0)
        vals.index = ee_v.index
    elif isinstance(sd, dict):
        vals = pd.Series(np.asarray(sd["p_mp"], dtype=float), index=ee_v.index).clip(lower=0.0)
    else:
        raise TypeError("Unexpected pvlib.singlediode return type.")
    if not np.isfinite(vals).all():
        raise ValueError("Electrical solver returned non-finite power at valid irradiance.")
    out.loc[valid] = vals
    return out


def cec_stc_fit_residuals(row: pd.Series) -> dict:
    """Evaluate the fitted CEC model at STC and expose datasheet residuals.

    This is an internal fit diagnostic, not an IEC conformity result.
    """
    fit = fit_cec_from_datasheet(row)
    photocurrent, saturation_current, resistance_series, resistance_shunt, nNsVth = pvlib.pvsystem.calcparams_cec(
        effective_irradiance=1000.0,
        temp_cell=25.0,
        alpha_sc=fit["alpha_sc_A_C"],
        a_ref=fit["a_ref"],
        I_L_ref=fit["I_L_ref"],
        I_o_ref=fit["I_o_ref"],
        R_sh_ref=fit["R_sh_ref"],
        R_s=fit["R_s"],
        Adjust=fit["Adjust"],
    )
    sd = pvlib.pvsystem.singlediode(
        photocurrent=photocurrent,
        saturation_current=saturation_current,
        resistance_series=resistance_series,
        resistance_shunt=resistance_shunt,
        nNsVth=nNsVth,
        method="lambertw",
    )
    modeled = {
        "pmp_w": float(sd["p_mp"]),
        "voc_v": float(sd["v_oc"]),
        "isc_a": float(sd["i_sc"]),
        "vmp_v": float(sd["v_mp"]),
        "imp_a": float(sd["i_mp"]),
    }
    datasheet = {
        "pmp_w": float(row["pmax_w"]),
        "voc_v": float(row["voc_v"]),
        "isc_a": float(row["isc_a"]),
        "vmp_v": float(row["vmp_v"]),
        "imp_a": float(row["imp_a"]),
    }
    result = {
        "module_id": row["module_id"],
        "manufacturer": row["manufacturer"],
        "model": row["model"],
        "irradiance_w_m2": 1000.0,
        "cell_temperature_c": 25.0,
        "fit_scope": "cec_single_diode_datasheet_fit_internal_diagnostic",
    }
    for name in ["pmp_w", "voc_v", "isc_a", "vmp_v", "imp_a"]:
        result[f"datasheet_{name}"] = datasheet[name]
        result[f"modeled_{name}"] = modeled[name]
        result[f"residual_{name}"] = modeled[name] - datasheet[name]
        result[f"residual_{name}_pct"] = 100.0 * (modeled[name] - datasheet[name]) / datasheet[name]
    return result


def _pmp_for_model(
    effective_irradiance: pd.Series,
    temp_module_c: pd.Series,
    row: pd.Series,
    model_policy: dict,
) -> tuple[pd.Series, dict]:
    if model_policy["electrical_model"] == "iec61853_module_specific_matrix":
        matrix = read_iec61853_matrix(model_policy["matrix_path"])
        val = validate_iec61853_matrix(
            matrix,
            module_pmax_w=float(row["pmax_w"]),
            source_status="module_specific_measured",
        )
        p, diag = interpolate_iec61853_pmax(matrix, effective_irradiance, temp_module_c)
        diag.update({
            "matrix_measured_points": val.measured_points,
            "matrix_has_stc_anchor": val.has_stc_anchor,
            "matrix_stc_relative_error_pct": val.stc_relative_error_pct,
        })
        return p.set_axis(effective_irradiance.index), diag

    fit = fit_cec_from_datasheet(row)
    p = _pmp_from_cec(effective_irradiance, temp_module_c, fit)
    return p, {
        "matrix_measured_points": 0,
        "matrix_has_stc_anchor": False,
        "matrix_stc_relative_error_pct": np.nan,
        "matrix_irradiance_extrapolation_fraction_pct": np.nan,
        "matrix_temperature_extrapolation_fraction_pct": np.nan,
        "matrix_nearest_fallback_fraction_pct": np.nan,
        "matrix_interpolation_policy": "not_applicable_cec_single_diode",
    }


def simulate_module_hourly(
    weather: pd.DataFrame,
    row: pd.Series,
    common_soiling_loss_pct: float = 2.0,
    root: str | Path | None = None,
    bifacial_config: dict | None = None,
) -> tuple[dict, pd.DataFrame]:
    """Simulate one commercial module without technology-score shortcuts.

    The primary annual energy is broadband unless module-specific spectral evidence is
    available. Technology-class spectral response is retained only as a sensitivity.
    Thin-film/non-c-Si candidates without module-specific performance-matrix evidence are
    explicitly marked decision-ineligible to prevent single-diode model-form bias.
    """
    require_pvlib()
    validate_module_candidates(pd.DataFrame([row]))

    model_policy = electrical_model_policy(row, root)
    spectral_policy = spectral_evidence_policy(row)
    thermal_policy = thermal_evidence_policy(row)

    soiling_ratio = 1.0 - max(0.0, min(100.0, float(common_soiling_loss_pct))) / 100.0
    poa_candidate = candidate_plane_of_array(weather, row, bifacial_config=bifacial_config)
    poa_raw = poa_candidate["front_reference_w_m2"]
    poa_optical = poa_candidate["front_optical_w_m2"]
    poa_effective = poa_candidate["effective_electrical_poa_w_m2"]
    spectrum = spectral_factor_for_module(
        weather, row, strict=bool(spectral_policy["spectral_decision_eligible"])
    )
    # Rear-side thermal coupling is not assigned an invented absorption coefficient.
    # Temperature remains driven by front optical POA until candidate/mount-specific
    # thermal evidence supports a rear-inclusive thermal calibration.
    temp_module, temp_cell = module_operating_temperatures(weather, row, poa_global_w_m2=poa_optical)
    electrical_temperature = (
        temp_module if model_policy["electrical_model"] == "iec61853_module_specific_matrix" else temp_cell
    )

    effective_broadband = (poa_effective * soiling_ratio).clip(lower=0.0)
    effective_front_only = (poa_optical * soiling_ratio).clip(lower=0.0)
    effective_spectral_proxy = (poa_effective * spectrum * soiling_ratio).clip(lower=0.0)

    daylight = pd.to_numeric(weather["poa_w_m2"], errors="coerce") > 20
    if daylight.any() and (not np.isfinite(effective_broadband[daylight]).all() or not np.isfinite(electrical_temperature[daylight]).all()):
        raise ValueError("Invalid daytime irradiance or temperature; no ranking can be produced.")
    exploratory_model_failure = ""
    try:
        pmp_broadband, model_diag = _pmp_for_model(
            effective_broadband, electrical_temperature, row, model_policy
        )
        pmp_spectral, _ = _pmp_for_model(
            effective_spectral_proxy, electrical_temperature, row, model_policy
        )
    except Exception as exc:
        # A decision-eligible candidate must still fail closed: no hidden electrical
        # substitute is permitted. A candidate already barred by the evidence policy
        # (for example CdTe without module-specific IEC 61853 evidence) remains visible
        # with NaN energy rather than crashing the entire comparison.
        if bool(model_policy["decision_eligible"]):
            raise
        exploratory_model_failure = str(exc)
        pmp_broadband = pd.Series(np.nan, index=weather.index, dtype=float)
        pmp_spectral = pd.Series(np.nan, index=weather.index, dtype=float)
        model_diag = {
            "matrix_measured_points": 0,
            "matrix_has_stc_anchor": False,
            "matrix_stc_relative_error_pct": np.nan,
            "matrix_irradiance_extrapolation_fraction_pct": np.nan,
            "matrix_temperature_extrapolation_fraction_pct": np.nan,
            "matrix_nearest_fallback_fraction_pct": np.nan,
            "matrix_interpolation_policy": "not_available_exploratory_model_failed",
        }

    # Physics-driver diagnostics use the same model and geometry as the primary run.
    # They are ablations, not separate scores: (a) hold electrical temperature at
    # 25°C; (b) remove rear contribution while preserving front row geometry.
    if pmp_broadband.notna().any():
        temp_25 = pd.Series(25.0, index=weather.index, dtype=float)
        pmp_at_25c, _ = _pmp_for_model(effective_broadband, temp_25, row, model_policy)
        pmp_front_only, _ = _pmp_for_model(effective_front_only, electrical_temperature, row, model_policy)
    else:
        pmp_at_25c = pd.Series(np.nan, index=weather.index, dtype=float)
        pmp_front_only = pd.Series(np.nan, index=weather.index, dtype=float)

    pmax = float(row["pmax_w"])
    specific_broadband = pmp_broadband / pmax
    specific_spectral = pmp_spectral / pmax
    weights = pd.to_numeric(
        weather.get("days_weight", pd.Series(1.0, index=weather.index)), errors="coerce"
    ).fillna(1.0)
    broadband_yield = float((specific_broadband * weights).sum(min_count=1))
    if not exploratory_model_failure and (not np.isfinite(broadband_yield) or broadband_yield <= 0):
        raise ValueError("No positive finite energy was calculated; no ranking is available.")
    spectral_yield = float((specific_spectral * weights).sum(min_count=1))
    yield_at_25c = float(((pmp_at_25c / pmax) * weights).sum(min_count=1))
    front_only_yield = float(((pmp_front_only / pmax) * weights).sum(min_count=1))
    linear_irradiance_reference = float(((effective_broadband / 1000.0) * weights).sum(min_count=1))
    off_stc_irradiance_response_pct = (
        (yield_at_25c / linear_irradiance_reference - 1.0) * 100.0
        if linear_irradiance_reference > 0 and np.isfinite(yield_at_25c) else np.nan
    )
    temperature_response_effect_pct = (
        (broadband_yield / yield_at_25c - 1.0) * 100.0
        if yield_at_25c > 0 and np.isfinite(broadband_yield) else np.nan
    )
    bifacial_rear_gain_pct = (
        (broadband_yield / front_only_yield - 1.0) * 100.0
        if front_only_yield > 0 and np.isfinite(broadband_yield) else 0.0
    )

    # Primary decision energy does not use a generic technology-class spectral proxy.
    if spectral_policy["spectral_decision_eligible"]:
        decision_yield = spectral_yield
        decision_spectral_basis = "module_specific_spectral_evidence"
    else:
        decision_yield = broadband_yield
        decision_spectral_basis = "broadband_primary_technology_class_spectral_is_sensitivity_only"

    daylight = poa_optical > 20.0
    summary = {
        "module_id": row["module_id"],
        "technology_id": row["technology_id"],
        "manufacturer": row["manufacturer"],
        "model": row["model"],
        "technology_label": row.get("technology_label", ""),
        "annual_dc_specific_energy_kwh_kwp": decision_yield,
        "annual_yield_kwh_kwp": decision_yield,
        "annual_dc_specific_energy_broadband_kwh_kwp": broadband_yield,
        "annual_dc_specific_energy_no_spectral_kwh_kwp": broadband_yield,
        "annual_dc_specific_energy_spectral_sensitivity_kwh_kwp": spectral_yield,
        "annual_yield_no_spectral_kwh_kwp": broadband_yield,
        "annual_front_surface_poa_kwh_m2": float((poa_raw * weights).sum() / 1000.0),
        "annual_optically_effective_poa_kwh_m2": float((poa_optical * weights).sum() / 1000.0),
        "annual_rear_optical_poa_kwh_m2": float((poa_candidate["rear_optical_w_m2"] * weights).sum() / 1000.0),
        "annual_rear_front_equivalent_poa_kwh_m2": float((poa_candidate["rear_equivalent_w_m2"] * weights).sum() / 1000.0),
        "bifaciality_factor": float(poa_candidate["bifaciality_factor"]),
        "rear_irradiance_model_active": bool(poa_candidate["rear_irradiance_model_active"]),
        "poa_geometry_basis": poa_candidate["poa_geometry_basis"],
        "rear_model_note": poa_candidate["rear_model_note"],
        "front_only_annual_yield_kwh_kwp": front_only_yield,
        "bifacial_rear_gain_pct": bifacial_rear_gain_pct,
        "annual_yield_at_25c_kwh_kwp": yield_at_25c,
        "linear_irradiance_reference_kwh_kwp": linear_irradiance_reference,
        "off_stc_irradiance_response_pct": off_stc_irradiance_response_pct,
        "temperature_response_effect_pct": temperature_response_effect_pct,
        "iam_effect_pct": (float((poa_optical * weights).sum() / max((poa_raw * weights).sum(), 1e-9)) - 1.0) * 100.0,
        "spectral_effect_pct": ((spectral_yield / broadband_yield - 1.0) * 100.0 if broadband_yield > 0 else np.nan),
        "avg_module_temperature_c_daylight": float(temp_module[daylight].mean()) if daylight.any() else np.nan,
        "p95_module_temperature_c_daylight": float(temp_module[daylight].quantile(0.95)) if daylight.any() else np.nan,
        "avg_cell_temperature_c_daylight": float(temp_cell[daylight].mean()) if daylight.any() else np.nan,
        "p95_cell_temperature_c_daylight": float(temp_cell[daylight].quantile(0.95)) if daylight.any() else np.nan,
        "max_cell_temperature_c": float(temp_cell.max()),
        "mean_spectral_factor_daylight": float(spectrum[daylight].mean()) if daylight.any() else 1.0,
        "electrical_model": model_policy["electrical_model"],
        "decision_eligible": bool(model_policy["decision_eligible"]),
        "model_evidence_level": model_policy["model_evidence_level"],
        "model_form_warning": model_policy["model_form_warning"],
        "spectral_decision_eligible": bool(spectral_policy["spectral_decision_eligible"]),
        "spectral_evidence_level": spectral_policy["spectral_evidence_level"],
        "spectral_policy": spectral_policy["spectral_policy"],
        "spectral_proxy_status": spectrum.attrs.get("spectral_proxy_status", "unknown"),
        "spectral_proxy_note": spectrum.attrs.get("spectral_proxy_note", ""),
        "spectral_proxy_invalid_daylight_hours": int(spectrum.attrs.get("spectral_proxy_invalid_daylight_hours", 0)),
        "spectral_proxy_invalid_daylight_fraction_pct": float(spectrum.attrs.get("spectral_proxy_invalid_daylight_fraction_pct", 0.0)),
        "spectral_proxy_valid_daylight_fraction_pct": float(spectrum.attrs.get("spectral_proxy_valid_daylight_fraction_pct", 100.0)),
        "spectral_proxy_fallback_policy": spectrum.attrs.get("spectral_proxy_fallback_policy", "none"),
        "decision_spectral_basis": decision_spectral_basis,
        "exploratory_electrical_model_failure": exploratory_model_failure,
        "soiling_basis": "common_site_assumption_no_technology_score",
        "soiling_loss_pct": float(common_soiling_loss_pct),
        "thermal_model": thermal_policy["thermal_model"],
        "thermal_evidence_level": thermal_policy["thermal_evidence_level"],
        **model_diag,
    }

    hourly = weather.copy()
    # Preserve the actual simulation timestamp as a first-class export field.
    # This keeps client CSVs self-describing and enables monthly/seasonal report charts.
    if "timestamp" not in hourly.columns:
        if "time_utc" in hourly.columns:
            ts = pd.to_datetime(hourly["time_utc"], utc=True, errors="coerce")
        elif isinstance(hourly.index, pd.DatetimeIndex):
            ts = pd.to_datetime(hourly.index, utc=True, errors="coerce")
        else:
            raise ValueError("Hourly simulation lost its physical timestamp; cannot build seasonal or interannual diagnostics.")
        hourly.insert(0, "timestamp", ts)
    hourly["module_id"] = row["module_id"]
    hourly["module_temperature_c"] = temp_module
    hourly["module_cell_temperature_c"] = temp_cell
    hourly["electrical_model_temperature_c"] = electrical_temperature
    hourly["spectral_factor"] = spectrum
    hourly["spectral_proxy_fallback_applied"] = spectrum.attrs.get(
        "spectral_proxy_invalid_daylight_mask", pd.Series(False, index=weather.index)
    ).reindex(weather.index, fill_value=False).astype(bool)
    hourly["front_optical_poa_w_m2"] = poa_optical
    hourly["rear_optical_poa_w_m2"] = poa_candidate["rear_optical_w_m2"]
    hourly["rear_equivalent_poa_w_m2"] = poa_candidate["rear_equivalent_w_m2"]
    hourly["effective_electrical_poa_w_m2"] = poa_effective
    hourly["effective_irradiance_broadband_w_m2"] = effective_broadband
    hourly["effective_irradiance_spectral_proxy_w_m2"] = effective_spectral_proxy
    hourly["effective_irradiance_w_m2"] = effective_broadband
    hourly["module_pmp_broadband_w"] = pmp_broadband
    hourly["module_pmp_spectral_proxy_w"] = pmp_spectral
    hourly["module_pmp_w"] = pmp_broadband if not spectral_policy["spectral_decision_eligible"] else pmp_spectral
    hourly["specific_power_kw_per_kwp"] = hourly["module_pmp_w"] / pmax
    return summary, hourly
