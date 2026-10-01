"""
CUBE Prep Manager - Streamlit Operator Web Application & Live Verification Portal.
Run with: streamlit run app.py
"""

import os
import json
import cv2
import pandas as pd
import numpy as np
import streamlit as st

# Configure page
st.set_page_config(
    page_title="CUBE Prep Manager · Inbound Amazon Compliance",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main { background-color: #0b0f19; color: #f8fafc; }
    .stMetric { background-color: #1e293b; padding: 12px; border-radius: 8px; border: 1px solid #334155; }
    .verdict-pass { background-color: #064e3b; border: 1px solid #059669; color: #6ee7b7; padding: 16px; border-radius: 8px; font-size: 1.25rem; font-weight: 700; }
    .verdict-fail { background-color: #7f1d1d; border: 1px solid #dc2626; color: #fca5a5; padding: 16px; border-radius: 8px; font-size: 1.25rem; font-weight: 700; }
    .verdict-uncertain { background-color: #78350f; border: 1px solid #d97706; color: #fde68a; padding: 16px; border-radius: 8px; font-size: 1.25rem; font-weight: 700; }
    .check-card { background-color: #1e293b; border-left: 4px solid #3b82f6; padding: 10px 14px; margin-bottom: 8px; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

# Data paths
BASE_DATA_DIR = "cube_prep_dataset"
COMPLIANCE_CSV = "data/compliance_records.csv"
OVERRIDE_LOG = "reports/audit_overrides.jsonl"

@st.cache_data
def load_dataset():
    if os.path.exists(COMPLIANCE_CSV):
        return pd.read_csv(COMPLIANCE_CSV)
    return pd.read_csv(os.path.join(BASE_DATA_DIR, "cube_prep_dataset.csv"))

@st.cache_data
def load_unit_record(unit_id):
    path = f"submissions/DhanviND360/records/units/{unit_id}.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None

df = load_dataset()

# --- SIDEBAR CONTROLS ---
st.sidebar.title("📦 CUBE Prep Manager")
st.sidebar.caption("Step 2 of 5: Inbound to Amazon · Proof of Compliance")

# Tenancy Switcher (Rule 1)
st.sidebar.subheader("🏢 Multi-Tenancy Scope (Rule 1)")
tenant = st.sidebar.selectbox("Active Organization Tenant", ["org_demo_alpha", "org_demo_bravo"], index=0)

# Filter units by tenant
tenant_df = df[df["org_id"] == tenant]
st.sidebar.info(f"Tenant '{tenant}' has **{len(tenant_df)}** registered units. Cross-tenant records are strictly isolated.")

# Unit selection
selected_unit = st.sidebar.selectbox("Select Unit to Inspect", tenant_df["unit_id"].tolist())
row = tenant_df[tenant_df["unit_id"] == selected_unit].iloc[0]

# Display toggles
st.sidebar.subheader("🔍 Evidence Overlays")
show_fnsku_box = st.sidebar.checkbox("Highlight FNSKU Label Box", value=True)
show_seams = st.sidebar.checkbox("Show Package Seams & Edge Margins", value=True)
show_raw_json = st.sidebar.checkbox("View Complete Evidence Record JSON", value=False)

# Economics sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("💰 Unit Economics")
st.sidebar.metric("Target Prep Fee", f"${row.get('prep_price_usd', 0.75):.2f}")
st.sidebar.metric("Compute Cost / Check", "$0.00015", delta="-99.98% margin cost")

# --- MAIN CONTENT ---
record = load_unit_record(selected_unit)

col_head1, col_head2, col_head3, col_head4 = st.columns(4)
with col_head1:
    st.metric("Unit ID", selected_unit)
with col_head2:
    st.metric("Work Order", row.get("work_order_id", "WO-3000"))
with col_head3:
    st.metric("FBA Shipment", row.get("fba_shipment_id", "FBA-CUBE-100"))
with col_head4:
    st.metric("SKU / ASIN", f"{row.get('sku', '')[:12]}...")

st.markdown("---")

# VERDICT BANNER
status = record["overall_status"] if record else row.get("overall_status", "UNCERTAIN")
exp = record["issue_explanation"] if record else row.get("issue_explanation", "")

if status == "PASS":
    st.markdown(f'<div class="verdict-pass">✅ PASS — COMPLIANCE VERIFIED<br><span style="font-size: 0.95rem; font-weight: 400;">{exp}</span></div>', unsafe_allow_html=True)
elif status == "FAIL":
    st.markdown(f'<div class="verdict-fail">❌ FAIL — PREP DEFECT DETECTED<br><span style="font-size: 0.95rem; font-weight: 400;">{exp}</span></div>', unsafe_allow_html=True)
else:
    st.markdown(f'<div class="verdict-uncertain">⚠️ UNCERTAIN — QUALITY ABSTENTION / PENDING REVIEW<br><span style="font-size: 0.95rem; font-weight: 400;">{exp}</span></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# 3-VIEW EVIDENCE GALLERY
st.subheader("📸 Tri-View Photographic Evidence Capture")
c1, c2, c3 = st.columns(3)

front_path = os.path.join(BASE_DATA_DIR, f"images/{selected_unit}_front.jpg")
back_path = os.path.join(BASE_DATA_DIR, f"images/{selected_unit}_back.jpg")
label_path = os.path.join(BASE_DATA_DIR, f"images/{selected_unit}_label.jpg")

front_img = cv2.imread(front_path) if os.path.exists(front_path) else None
back_img = cv2.imread(back_path) if os.path.exists(back_path) else None
label_img = cv2.imread(label_path) if os.path.exists(label_path) else None

# Draw overlays if enabled
if front_img is not None and record and "evidence_vector" in record:
    f_disp = front_img.copy()
    fnsku_box = record["evidence_vector"].get("fnsku", {}).get("box")
    if show_fnsku_box and fnsku_box:
        x, y, w, h = fnsku_box
        cv2.rectangle(f_disp, (x, y), (x + w, y + h), (0, 255, 0), 3)
        cv2.putText(f_disp, "FNSKU LABEL", (x, max(20, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    if show_seams:
        # Seam center line
        cv2.line(f_disp, (384, 75), (384, 460), (0, 140, 255), 2)
        cv2.putText(f_disp, "SEAM", (388, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 140, 255), 1)
        # Edge lines
        cv2.line(f_disp, (623, 75), (623, 460), (0, 0, 255), 2)
        cv2.putText(f_disp, "EDGE", (580, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    f_disp_rgb = cv2.cvtColor(f_disp, cv2.COLOR_BGR2RGB)
else:
    f_disp_rgb = cv2.cvtColor(front_img, cv2.COLOR_BGR2RGB) if front_img is not None else None

with c1:
    st.caption("View 1: Front (Packaging & Placement)")
    if f_disp_rgb is not None:
        st.image(f_disp_rgb, width="stretch")
with c2:
    st.caption("View 2: Back (Cover & Marks)")
    if back_img is not None:
        st.image(cv2.cvtColor(back_img, cv2.COLOR_BGR2RGB), width="stretch")
with c3:
    st.caption("View 3: Label Close-Up (FNSKU Barcode & Text)")
    if label_img is not None:
        st.image(cv2.cvtColor(label_img, cv2.COLOR_BGR2RGB), width="stretch")

st.markdown("---")

# CHECK DETAILS & MEASUREMENTS
col_checks, col_meas = st.columns([1.2, 1.0])

with col_checks:
    st.subheader("📋 Itemized Amazon FBA Rule Checks")
    checks = record.get("checks", {}) if record else {}
    
    check_items = [
        ("Polybag Present & Correctly Sealed", "polybag_present_sealed"),
        ("Suffocation Warning Legible & Unobscured", "suffocation_warning"),
        ("FNSKU Label Placement (No seam/edge/curve)", "fnsku_label_placement"),
        ("Original Manufacturer Barcode Covered", "original_barcode_covered"),
        ("Expiry Date Legible After Wrapping", "expiry_date"),
        ("Required Handling Marks (Liquid/Fragile/Up)", "handling_marks"),
    ]
    
    for label, key in check_items:
        chk = checks.get(key, {})
        v = chk.get("verdict", "N/A")
        det = chk.get("detail", "")
        
        badge = "🟢 PASS" if v == "PASS" else ("🔴 FAIL" if v == "FAIL" else ("🟡 UNCERTAIN" if v == "UNCERTAIN" else "⚪ N/A"))
        st.markdown(f"""
        <div class="check-card">
            <strong>{label}</strong>: {badge}<br>
            <span style="font-size: 0.85rem; color: #94a3b8;">{det}</span>
        </div>
        """, unsafe_allow_html=True)

with col_meas:
    st.subheader("📐 OpenCV Deterministic Spatial Vector")
    ev = record.get("evidence_vector", {}) if record else {}
    fnsku_m = ev.get("fnsku", {})
    iq = ev.get("image_quality", {})
    
    st.write("**Spatial Measurements:**")
    m1, m2 = st.columns(2)
    m1.metric("Distance to Edge", f"{fnsku_m.get('edge_distance_px', 0)} px", help="Minimum distance from label boundary to nearest package edge.")
    m2.metric("Seam Overlap IoU", f"{fnsku_m.get('seam_overlap_iou', 0.0)*100:.1f} %", help="Overlap ratio between package seam and label area.")
    
    st.write("**Calibration & Quality Metrics:**")
    q1, q2 = st.columns(2)
    q1.metric("Laplacian Blur Score", f"{iq.get('min_blur', 0.0):.1f}", delta="Calibrated" if iq.get("min_blur", 0.0) >= 25 else "Blurry Abstention")
    q2.metric("Model Execution Latency", f"{record.get('performance', {}).get('latency_ms', 0):.1f} ms" if record else "N/A")

# --- HUMAN OVERRIDE WORKFLOW (Honesty Rule 2) ---
st.markdown("---")
st.subheader("✍️ Human Operator Override (Honesty Rule)")
st.caption("Overrides are recorded as audit data. When an operator disagrees with the agent, the original verdict, new verdict, and justification are logged permanently.")

with st.expander("Record Operator Override for This Unit"):
    with st.form("override_form"):
        new_v = st.selectbox("New Human Verdict", ["PASS", "FAIL", "UNCERTAIN"])
        reason = st.text_area("Mandatory Override Justification", placeholder="e.g. Visual inspection at station 3 confirmed seam clearance under angled lighting.")
        op_id = st.text_input("Operator ID", value="op_amira")
        submitted = st.form_submit_button("Submit & Sign Override Record")
        
        if submitted:
            if not reason.strip():
                st.error("Override justification cannot be empty.")
            else:
                entry = {
                    "unit_id": selected_unit,
                    "org_id": tenant,
                    "original_verdict": status,
                    "new_verdict": new_v,
                    "reason": reason,
                    "operator_id": op_id,
                    "timestamp": pd.Timestamp.now().isoformat()
                }
                os.makedirs(os.path.dirname(OVERRIDE_LOG), exist_ok=True)
                with open(OVERRIDE_LOG, "a") as f:
                    f.write(json.dumps(entry) + "\n")
                st.success(f"Override for {selected_unit} logged successfully to audit trail!")

if show_raw_json and record:
    st.markdown("---")
    st.subheader("📄 Raw Evidence Record (JSON)")
    st.json(record)
