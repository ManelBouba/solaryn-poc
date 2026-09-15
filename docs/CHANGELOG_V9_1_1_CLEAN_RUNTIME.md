# SOLARYN V9.1.1 — Clean Runtime Patch

This patch does **not** change the V9 decision policy, energy evidence hierarchy, module data, uncertainty guardrail, or spectral decision rules.

Changes:
- Replaced deprecated Streamlit `use_container_width=True` with `width="stretch"` for native Streamlit widgets.
- Kept `st_folium(..., use_container_width=True)` unchanged because it is a third-party component API.
- CEC IV simulation now skips exact-zero/nonfinite irradiance hours and sets their power to zero before solving the single-diode model. This avoids degenerate night-time numerical solves and does not alter daylight physics.
- No cross-technology evidence gate was removed. CdTe still requires decision-grade evidence for a robust cross-technology winner.
