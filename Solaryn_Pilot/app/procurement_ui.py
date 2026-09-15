"""Procurement workspace layered onto the existing physics pilot."""
from dataclasses import asdict
import json
import pandas as pd
import streamlit as st
from src.procurement_model import Project, Candidate, compare, screening_physics
from src.procurement_store import save, history, read, report


def render_procurement(root):
    st.caption("SOLARYN / PROCUREMENT WORKSPACE")
    st.title("From module offers to lifetime value")
    st.write("Compare net AC yield, lifecycle assumptions and exact-product evidence in a reproducible decision.")
    st.info("Local single-user MVP. Example candidates are synthetic assumptions. Financial rankings require engineering review; cloud accounts and tenant isolation are not implemented.")
    setup, evidence, scenarios, physics, archive = st.tabs(
        ["Project & offers", "Evidence & climate", "Decision explorer", "Physics & equations", "Saved decisions"])
    db = root / "workspace" / "procurement.sqlite3"
    with setup:
        left, right = st.columns(2)
        with left:
            name = st.text_input("Project name", "Riyadh procurement study")
            capacity = st.number_input("DC capacity (MWp)", .001, 100000., 100.)
            years = st.number_input("Design life (years)", 1, 60, 30)
            rate = st.number_input("Real discount rate (%)", 0., 100., 7.) / 100
            ppa = st.number_input("Constant PPA (EUR/MWh)", 0., 10000., 45.)
        with right:
            bos = st.number_input("Common non-module CAPEX (EUR/Wp)", 0., 100., .40)
            om = st.number_input("O&M excluding cleaning (EUR/kWp/year)", 0., 10000., 10.)
            cleaning = st.number_input("Cleaning (EUR/kWp/year)", 0., 10000., 2.)
            debt = st.number_input("Annual debt service for DSCR proxy (EUR; 0 disables)", 0., 1e12, 0.)
        project = Project(name, capacity, int(years), rate, ppa, bos, om, cleaning, debt)
        st.subheader("Candidate offers")
        st.caption("Net AC yield must already include inverter, clipping, soiling, availability and curtailment losses. Early loss and additional loss default to zero to avoid counting losses twice. Fractions use 0.005 = 0.5%.")
        defaults = pd.DataFrame([asdict(Candidate("Candidate A", "Example A", "Unknown", .11, 1850., "Synthetic example — replace", event_year=min(15, years))),
                                 asdict(Candidate("Candidate B", "Example B", "Unknown", .13, 1880., "Synthetic example — replace", degradation=.004, event_year=min(15, years)))])
        upload = st.file_uploader("Import normalized offers (JSON list)", type=["json"], key="proc_offers")
        if upload:
            try:
                records = json.loads(upload.getvalue())
                if not isinstance(records, list) or not 2 <= len(records) <= 20:
                    raise ValueError("Upload a list of 2–20 candidate objects")
                defaults = pd.DataFrame([asdict(Candidate(**r)) for r in records])
            except (ValueError, TypeError) as exc:
                st.error(f"Invalid offers: {exc}")
                st.stop()
        offers = st.data_editor(defaults, num_rows="dynamic", hide_index=True, key="proc_candidates")
        st.download_button("Download offers template", defaults.to_json(orient="records", indent=2), "offers.json", "application/json")
    with evidence:
        st.subheader("Evidence register")
        st.write("Record a source and section for each claim. Reviews match the candidate name, exact model, BOM, field and current value; changing an input invalidates its prior match.")
        st.caption("Supported gate fields: net_ac_kwh_kwp, quote_eur_w, degradation, bom. Reviewer names are self-declared in this local pilot. Store source documents in your controlled repository and reference them here.")
        initial = pd.DataFrame([dict(candidate="Candidate A", model="Example A", bom="Unknown", field="net_ac_kwh_kwp",
                                     value="1850.0", source="Synthetic example", section="", classification="Assumption",
                                     status="Unreviewed", reviewer="", date="")])
        claims = st.data_editor(initial, num_rows="dynamic", hide_index=True, key="proc_claims",
                               column_config={"status": st.column_config.SelectboxColumn(options=["Unreviewed", "Reviewed", "Rejected"]),
                                              "classification": st.column_config.SelectboxColumn(options=["Fact", "Assumption", "Model output", "Expert judgment"])}).fillna("").to_dict("records")
        st.subheader("Climate evidence checklist")
        stressors = st.multiselect("Site stressors (user-declared)", ["Heat", "Dust / soiling", "Humidity", "Salt", "Hail / wind", "UV"], default=["Heat", "Dust / soiling", "UV"])
        mapping = {"Heat": ("Thermal cycling and temperature-related power loss", "Request mounting-specific thermal coefficients and exact-product test evidence"),
                   "Dust / soiling": ("Optical losses and nonuniform deposition", "Obtain site soiling measurements and cleaning cost scenarios"),
                   "Humidity": ("Moisture ingress, corrosion and insulation degradation", "Request BOM-matched damp-heat / field evidence"),
                   "Salt": ("Corrosion", "Review salt-mist evidence and installation details"),
                   "Hail / wind": ("Glass, cell and structural damage", "Review site loads, exact construction tests and tracker stow design"),
                   "UV": ("Encapsulant and polymer aging", "Request BOM-specific UV durability evidence")}
        risks = [{"stressor": s, "potential_mechanism": mapping[s][0], "evidence_request": mapping[s][1],
                  "basis": "Qualitative engineering checklist; no failure probability"} for s in stressors]
        st.dataframe(pd.DataFrame(risks), hide_index=True)
    with scenarios:
        st.subheader("Decision explorer")
        st.caption("Base case and downside controls are assumptions, not statistical quantiles. Replacement events use each candidate's event fields; recovered cost is an assumed cash recovery, not a warranty entitlement.")
        a, b = st.columns(2)
        degrade = a.slider("Additional annual degradation (percentage points)", 0., 2., 0., .05) / 100
        haircut = b.slider("Net AC yield haircut (%)", 0., 30., 0., .5) / 100
        try:
            candidates = [Candidate(**r) for r in offers.to_dict("records")]
            result = compare(project, candidates, claims, degrade, haircut)
        except (ValueError, TypeError, KeyError) as exc:
            st.error(f"Review inputs: {exc}")
            return
        result["climate_risks"] = risks
        st.warning(result["status"])
        best = result["results"][0]
        with st.container(horizontal=True):
            st.metric("Scenario leader", result["leader"] or "Tied", border=True)
            st.metric("Highest NPV", f"EUR {best['npv_eur']/1e6:,.2f}m", border=True)
            st.metric("Leader LCOE", f"EUR {best['lcoe_eur_mwh']:.2f}/MWh", border=True)
            st.metric("Missing reviewed claims", sum(len(r["evidence_gaps"]) for r in result["results"]), border=True)
        table = pd.DataFrame([{k: v for k, v in r.items() if k not in ["annual", "operating_value_eur"]} for r in result["results"]])
        st.dataframe(table, hide_index=True)
        st.caption(f"Price premiums are incremental operating value versus {candidates[0].name}, the first input offer, at equal installed DC capacity. A negative premium means a discount is needed.")
        energy = pd.DataFrame({r["candidate"]: [a["energy_mwh"] for a in r["annual"]] for r in result["results"]}, index=range(1, years + 1))
        energy.index.name = "Operating year"
        st.line_chart(energy, x_label="Operating year", y_label="Net AC energy (MWh)")
        with st.expander("Annual cash flows and DSCR proxy"):
            selected = st.selectbox("Candidate", [r["candidate"] for r in result["results"]])
            st.dataframe(pd.DataFrame(next(r["annual"] for r in result["results"] if r["candidate"] == selected)), hide_index=True)
            st.caption("DSCR proxy uses pre-tax operating cash after modeled replacements divided by constant debt service. It is not a lender CFADS calculation. IRR is a fraction; null means absent or ambiguous.")
        st.download_button("Download decision report", report(result), "procurement-decision.md", "text/markdown")
        st.download_button("Download exact calculation", json.dumps(result, indent=2, allow_nan=False), "procurement-decision.json", "application/json")
        if st.button("Save decision snapshot", type="primary"):
            st.success(f"Saved {save(db, result)}")
    with physics:
        st.subheader("Transparent physics screening")
        st.caption("Front-side POA interval calculator. This does not feed the imported AC yield automatically. Use Module Recommendation for the existing hourly electrical model.")
        a, b, c = st.columns(3)
        poa = a.number_input("Plane-of-array irradiance (W/m²)", 0., 2000., 800.)
        ambient = b.number_input("Ambient temperature (°C)", -90., 90., 35.)
        wind = c.number_input("Wind speed (m/s)", 0., 100., 2.)
        values = screening_physics(poa, ambient, wind)
        st.json(values)
        st.latex(r"T_m=T_a+\frac{G_{POA}}{U_0+U_1v},\quad T_c=T_m+\Delta T\frac{G_{POA}}{1000}")
        st.latex(r"P_{DC}/P_{STC}=\max(0,\frac{G_{POA}}{1000}[1+\gamma(T_c-25)])")
        st.latex(r"E_y=C_{MWp}Y_{AC}(1-L_0)(1-d)^{y-1}(1-L_a)(1-f_yD_y/365)")
        st.latex(r"NPV=-CAPEX+\sum_{y=1}^{N}\frac{R_y-O_y}{(1+r)^y},\quad LCOE=\frac{CAPEX+\sum O_y/(1+r)^y}{\sum E_y/(1+r)^y}")
        st.markdown((root / "docs" / "PROCUREMENT_MODEL.md").read_text(encoding="utf-8"))
    with archive:
        st.subheader("Saved decisions")
        rows = history(db)
        if rows:
            selected = st.selectbox("Saved snapshot", [r[0] for r in rows], format_func=lambda x: next(f"{r[2]} · {r[1]} · {r[0][:8]}" for r in rows if r[0] == x))
            try:
                old = read(db, selected)
                st.write(old["status"])
                st.download_button("Download saved calculation", json.dumps(old, indent=2), f"{selected}.json", "application/json")
                st.download_button("Download saved report", report(old), f"{selected}.md", "text/markdown")
            except ValueError as exc:
                st.error(str(exc))
        else:
            st.caption("Save a decision in the explorer to retain its inputs, evidence, scenario and annual results.")
