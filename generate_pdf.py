"""
Refined PDF Generator for 'Prep Manager - Orchestrator Integration Guide'.
Uses Preformatted flowables to render exact code indentation, line breaks,
and syntax structure. Produces an executive-grade 3-page guide.
"""

import os
import json
import fitz  # PyMuPDF
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable, Preformatted
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Running Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(36, 756, "CUBE 2026 | Prep Manager (Pod 02) - Orchestrator Integration Guide")
            self.drawRightString(576, 756, "API & Schema Contract v3.0")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(36, 749, 576, 749)
            
        # Running Footer (all pages)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(36, 36, 576, 36)
        
        self.drawString(36, 25, "CONFIDENTIAL - Cross-Pod Evidence Specification - CUBE Hackathon 2026")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(576, 25, page_str)
        self.restoreState()


def build_pdf(filename="PREP_MANAGER_ORCHESTRATOR_INTEGRATION_GUIDE.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=42,
        bottomMargin=42
    )

    styles = getSampleStyleSheet()

    # Color definitions
    NAVY = colors.HexColor("#0F172A")
    DARK_BLUE = colors.HexColor("#1E293B")
    BRAND_BLUE = colors.HexColor("#2563EB")
    LIGHT_BLUE = colors.HexColor("#F0F6FF")
    SLATE = colors.HexColor("#334155")
    MUTED = colors.HexColor("#64748B")
    BORDER_COLOR = colors.HexColor("#CBD5E1")
    LIGHT_BORDER = colors.HexColor("#E2E8F0")
    CODE_BG = colors.HexColor("#0B0F19")
    CALLOUT_BG = colors.HexColor("#F8FAFC")

    # Typography styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=NAVY,
        spaceAfter=2
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=MUTED,
        spaceAfter=6
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11.5,
        leading=15,
        textColor=NAVY,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=13,
        textColor=BRAND_BLUE,
        spaceBefore=6,
        spaceAfter=3,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11.5,
        textColor=SLATE,
        spaceAfter=4
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11.5,
        textColor=SLATE,
        leftIndent=10,
        spaceAfter=3
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.white
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        leading=9.5,
        textColor=SLATE
    )

    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7,
        leading=9.5,
        textColor=NAVY
    )

    code_pre_style = ParagraphStyle(
        'CodePreformatted',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=6.5,
        leading=8.2,
        textColor=colors.HexColor("#F8FAFC")
    )

    code_snip_style = ParagraphStyle(
        'CodeSnippetPre',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=6.2,
        leading=8.0,
        textColor=colors.HexColor("#0F172A")
    )

    callout_style = ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11.5,
        textColor=DARK_BLUE
    )

    story = []

    # =========================================================================
    # PAGE 1: Specification vs. Implementation & The API Endpoint
    # =========================================================================
    
    # Top Meta Bar
    meta_table = Table(
        [[
            Paragraph("<b>STAGE 02 | INBOUND PREP COMPLIANCE</b>", ParagraphStyle('M1', fontName='Helvetica-Bold', fontSize=7.5, leading=9, textColor=BRAND_BLUE)),
            Paragraph("<b>CUBE 2026 CROSS-POD CONTRACT</b>", ParagraphStyle('M2', fontName='Helvetica-Bold', fontSize=7.5, leading=9, textColor=MUTED, alignment=2))
        ]],
        colWidths=[320, 220]
    )
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 3))

    story.append(Paragraph("Prep Manager - Orchestrator Integration Guide", title_style))
    story.append(Paragraph("Technical Interface Specification | Core Adapter Endpoints | Evidence Record Schema | Operational SLAs", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.2, color=BRAND_BLUE, spaceBefore=0, spaceAfter=6))

    # Executive Summary Banner
    exec_text = (
        "<b>Executive Purpose:</b> This guide provides orchestrators (e.g. Saif's Master Orchestrator) with the "
        "authoritative contract to invoke inbound Amazon FBA prep compliance checks via the <b>Prep Manager Agent (Pod 02)</b>. "
        "It details the endpoint specification, payload formats, deterministic evidence records, and failure handling guarantees."
    )
    callout_data = [[Paragraph(exec_text, callout_style)]]
    callout_tbl = Table(callout_data, colWidths=[540])
    callout_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_BLUE),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#BFDBFE")),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(callout_tbl)
    story.append(Spacer(1, 6))

    # Section 1
    story.append(Paragraph("1. Specification vs. Implementation", h1_style))
    story.append(Paragraph(
        "A strict architectural boundary separates the cross-pod specification from Pod 02's internal implementation:",
        body_style
    ))

    spec_table_data = [
        [
            Paragraph("Dimension", table_header_style),
            Paragraph("Specification Requirement (The Role)", table_header_style),
            Paragraph("Agent Implementation (Pod 02 Solution)", table_header_style)
        ],
        [
            Paragraph("<b>Pipeline Position</b>", table_cell_bold),
            Paragraph("Step 02 in 5-pod inbound chain:<br/>Receiving (01) &rarr; Prep (02) &rarr; Pack (03) &rarr; Manifest (04) &rarr; Recovery (05).", table_cell_style),
            Paragraph("Accepts items post-arrival, inspects 3 camera angles (front, back, label), and emits machine-verifiable evidence records.", table_cell_style)
        ],
        [
            Paragraph("<b>Shared Identifier</b>", table_cell_bold),
            Paragraph("Strict join on shared foreign key <code>unit_id</code> (<code>UNIT-0001</code> through <code>UNIT-0100</code>).", table_cell_style),
            Paragraph("All records, photographic vectors, and telemetry key deterministically on <code>unit_id</code> and <code>org_id</code> tenant.", table_cell_style)
        ],
        [
            Paragraph("<b>Thin Adapter Mandate</b>", table_cell_bold),
            Paragraph("Agent must be a pure evaluation service. Multi-station routing, retries, and recovery claims belong to the orchestrator.", table_cell_style),
            Paragraph("Implemented as a stateless <code>POST /run</code> adapter. Contains zero cross-pod workflow routing, maintaining clean separation.", table_cell_style)
        ],
        [
            Paragraph("<b>Inspection Engine</b>", table_cell_bold),
            Paragraph("Verify FBA prep: polybag seals, suffocation warning, FNSKU placement, barcode coverage, expiry date, handling marks.", table_cell_style),
            Paragraph("Hardware-accelerated ONNX Nano detector (DirectML/GPU/CPU) + deterministic OpenCV spatial engine + Amazon FBA rule engine.", table_cell_style)
        ],
        [
            Paragraph("<b>Unit Economics</b>", table_cell_bold),
            Paragraph("Prep verification must fit prep fees ($0.40 - $1.10) with negligible compute overhead.", table_cell_style),
            Paragraph("Delivers sub-cent compute (~$0.00015 per inspection check), preserving &gt;99.9% of merchant operating margin.", table_cell_style)
        ]
    ]

    spec_tbl = Table(spec_table_data, colWidths=[90, 225, 225])
    spec_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(spec_tbl)
    story.append(Spacer(1, 6))

    # Section 2
    story.append(Paragraph("2. The API Endpoint", h1_style))
    story.append(Paragraph(
        "The service provides both the standardized <b>Round 3 Agent Adapter</b> (<code>/run</code>) for automated orchestration and high-performance direct endpoints for camera stations:",
        body_style
    ))

    endpoint_table_data = [
        [
            Paragraph("Endpoint", table_header_style),
            Paragraph("Method", table_header_style),
            Paragraph("Protocol / Payload", table_header_style),
            Paragraph("Primary Use Case & Description", table_header_style)
        ],
        [
            Paragraph("<b><code>/run</code></b>", table_cell_bold),
            Paragraph("<code>POST</code>", table_cell_style),
            Paragraph("<code>application/json</code>", table_cell_style),
            Paragraph("<b>Primary Orchestrator Adapter</b>. Conforms to Round 3 Agent I/O spec. Accepts image refs, runs inspection, and returns verdict with full evidence.", table_cell_style)
        ],
        [
            Paragraph("<b><code>/api/v1/inspect</code></b>", table_cell_bold),
            Paragraph("<code>POST</code>", table_cell_style),
            Paragraph("<code>application/json</code>", table_cell_style),
            Paragraph("Synchronous direct inspection endpoint using storage image references.", table_cell_style)
        ],
        [
            Paragraph("<b><code>/api/v1/inspect/stream</code></b>", table_cell_bold),
            Paragraph("<code>POST</code>", table_cell_style),
            Paragraph("<code>text/event-stream</code> (SSE)", table_cell_style),
            Paragraph("Reference-based progressive streaming across 5 milestones (front &rarr; back &rarr; label &rarr; done).", table_cell_style)
        ],
        [
            Paragraph("<b><code>/api/v1/inspect/stream/upload</code></b>", table_cell_bold),
            Paragraph("<code>POST</code>", table_cell_style),
            Paragraph("<code>multipart/form-data</code>", table_cell_style),
            Paragraph("Multipart direct camera image upload (front, back, label) with live SSE progress stream.", table_cell_style)
        ],
        [
            Paragraph("<b><code>/health</code></b> | <b><code>/health/ready</code></b>", table_cell_bold),
            Paragraph("<code>GET</code>", table_cell_style),
            Paragraph("<code>application/json</code>", table_cell_style),
            Paragraph("Liveness & readiness probes verifying ONNX runtime, detector model weights, and storage.", table_cell_style)
        ],
        [
            Paragraph("<b><code>/api/v1/records/{unit_id}</code></b>", table_cell_bold),
            Paragraph("<code>GET</code>", table_cell_style),
            Paragraph("<code>application/json</code>", table_cell_style),
            Paragraph("Retrieves stored historical evidence record with tenant row-level security isolation.", table_cell_style)
        ]
    ]

    ep_tbl = Table(endpoint_table_data, colWidths=[115, 38, 105, 282])
    ep_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(ep_tbl)
    story.append(Spacer(1, 5))

    # Connection and Authentication Box
    conn_text = (
        "<b>Base URLs:</b> Local: <code>http://localhost:8000</code> | Container/Cloud: Configured via <code>BACKEND_URL</code> environment variable.<br/>"
        "<b>Required Request Headers:</b><br/>"
        "&bull; <code>Content-Type: application/json</code><br/>"
        "&bull; <code>X-Org-ID: org_demo_alpha</code> or <code>org_demo_bravo</code> (Mandatory multi-tenancy header | Rule 1)<br/>"
        "&bull; <code>X-API-Key: &lt;SERVER_API_KEY&gt;</code> or <code>Authorization: Bearer &lt;TOKEN&gt;</code> (When <code>REQUIRE_AUTH=true</code>)"
    )
    conn_tbl = Table([[Paragraph(conn_text, callout_style)]], colWidths=[540])
    conn_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), CALLOUT_BG),
        ('BOX', (0, 0), (-1, -1), 1, LIGHT_BORDER),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(conn_tbl)

    # Page Break to Page 2
    story.append(PageBreak())

    # =========================================================================
    # PAGE 2: How to Send a Request
    # =========================================================================
    story.append(Paragraph("3. How to Send a Request", h1_style))
    story.append(Paragraph(
        "To invoke an inspection, send a <code>POST /run</code> request containing the unit identifier, multi-angle camera inputs, "
        "and specific work order rules. The adapter is resilient: images can be supplied as local file paths, HTTP URLs, or base64 strings.",
        body_style
    ))

    # Request Schema Table
    story.append(Paragraph("Input Request Parameters (POST /run):", h2_style))
    param_data = [
        [
            Paragraph("Parameter", table_header_style),
            Paragraph("Type", table_header_style),
            Paragraph("Required?", table_header_style),
            Paragraph("Description & Example Value", table_header_style)
        ],
        [
            Paragraph("<b><code>task_id</code></b>", table_cell_bold),
            Paragraph("<code>string</code>", table_cell_style),
            Paragraph("Optional", table_cell_style),
            Paragraph("Unique orchestrator execution ID. Auto-generated if omitted (e.g. <code>\"task-prep-0912-abc\"</code>).", table_cell_style)
        ],
        [
            Paragraph("<b><code>unit_id</code></b>", table_cell_bold),
            Paragraph("<code>string</code>", table_cell_style),
            Paragraph("<b>Required</b>", table_cell_bold),
            Paragraph("Foreign key identifier joining all 5 pods (e.g. <code>\"UNIT-0001\"</code>).", table_cell_style)
        ],
        [
            Paragraph("<b><code>org_id</code></b>", table_cell_bold),
            Paragraph("<code>string</code>", table_cell_style),
            Paragraph("<b>Required</b>", table_cell_bold),
            Paragraph("Tenant organization identifier: <code>\"org_demo_alpha\"</code> or <code>\"org_demo_bravo\"</code>.", table_cell_style)
        ],
        [
            Paragraph("<b><code>image_refs</code></b>", table_cell_bold),
            Paragraph("<code>object</code>", table_cell_style),
            Paragraph("<b>Required*</b>", table_cell_bold),
            Paragraph("Dict containing <code>\"front\"</code>, <code>\"back\"</code>, <code>\"label\"</code> image paths, URLs, or base64 strings.", table_cell_style)
        ],
        [
            Paragraph("<b><code>work_order</code></b>", table_cell_bold),
            Paragraph("<code>object</code>", table_cell_style),
            Paragraph("Optional", table_cell_style),
            Paragraph("Prep flags: <code>wo_polybag</code> (bool), <code>wo_suffocation_warning</code> (bool), <code>wo_expiry_date</code> (bool), <code>wo_handling_marks</code> (str).", table_cell_style)
        ],
        [
            Paragraph("<b><code>force_reinspect</code></b>", table_cell_bold),
            Paragraph("<code>boolean</code>", table_cell_style),
            Paragraph("Optional", table_cell_style),
            Paragraph("Defaults to <code>false</code>. Set <code>true</code> to bypass duplicate cache and force re-evaluation.", table_cell_style)
        ]
    ]

    param_tbl = Table(param_data, colWidths=[100, 45, 55, 340])
    param_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 2.8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.8),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(param_tbl)
    story.append(Spacer(1, 5))

    # Request JSON Payload Block
    story.append(Paragraph("Complete Request JSON Payload Example:", h2_style))
    req_json_str = """{
  "task_id": "orchestrator-task-0912-abc",
  "unit_id": "UNIT-0001",
  "org_id": "org_demo_alpha",
  "image_refs": {
    "front": "cube_prep_dataset/images/UNIT-0001_front.jpg",
    "back": "cube_prep_dataset/images/UNIT-0001_back.jpg",
    "label": "cube_prep_dataset/images/UNIT-0001_label.jpg"
  },
  "work_order": {
    "work_order_id": "WO-3000",
    "fba_shipment_id": "FBA-CUBE-100",
    "sku": "SKU-CABLE-USBC",
    "asin": "B0DUMMY261",
    "fnsku": "X00CUBE0001",
    "wo_polybag": false,
    "wo_suffocation_warning": false,
    "wo_expiry_date": false,
    "wo_handling_marks": "fragile",
    "prep_price_usd": 0.75
  },
  "force_reinspect": false
}"""

    code_tbl = Table([[Preformatted(req_json_str, code_pre_style)]], colWidths=[540])
    code_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), CODE_BG),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(code_tbl)
    story.append(Spacer(1, 5))

    # Invocation Code Snippets
    story.append(Paragraph("Ready-to-Use Orchestrator Code Snippets:", h2_style))

    curl_code = """curl -X POST http://localhost:8000/run \\
  -H "Content-Type: application/json" \\
  -H "X-Org-ID: org_demo_alpha" \\
  -d '{
    "task_id": "task-01",
    "unit_id": "UNIT-0001",
    "org_id": "org_demo_alpha",
    "image_refs": {
      "front": "images/UNIT-0001_front.jpg",
      "back": "images/UNIT-0001_back.jpg",
      "label": "images/UNIT-0001_label.jpg"
    },
    "work_order": {
      "wo_polybag": true,
      "wo_suffocation_warning": true
    }
  }'"""

    py_code = """import httpx

payload = {
    "task_id": "task-01",
    "unit_id": "UNIT-0001",
    "org_id": "org_demo_alpha",
    "image_refs": {
        "front": "images/UNIT-0001_front.jpg",
        "back": "images/UNIT-0001_back.jpg",
        "label": "images/UNIT-0001_label.jpg"
    },
    "work_order": {"wo_polybag": True}
}

resp = httpx.post(
    "http://localhost:8000/run",
    json=payload,
    headers={"X-Org-ID": "org_demo_alpha"},
    timeout=10.0
)
res = resp.json()
print("Verdict:", res["verdict"])"""

    snip_data = [
        [
            Paragraph("<b>cURL Command</b>", table_header_style),
            Paragraph("<b>Python (httpx / requests)</b>", table_header_style)
        ],
        [
            Preformatted(curl_code, code_snip_style),
            Preformatted(py_code, code_snip_style)
        ]
    ]

    snip_tbl = Table(snip_data, colWidths=[265, 275])
    snip_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#F1F5F9")),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(snip_tbl)

    # Page Break to Page 3
    story.append(PageBreak())

    # =========================================================================
    # PAGE 3: The Response (Evidence Record) & Important Integration Notes
    # =========================================================================
    story.append(Paragraph("4. The Response (Evidence Record) - Expected JSON Output", h1_style))
    story.append(Paragraph(
        "The response delivers a deterministic compliance verdict conforming strictly to <code>prep_evidence_contract.json</code>. "
        "It contains high-level orchestrator fields, itemized checks, spatial evidence vectors, and the complete audit record:",
        body_style
    ))

    resp_json_str = """{
  "task_id": "orchestrator-task-0912-abc",
  "agent": "prep",
  "stage": "prep",
  "org_id": "org_demo_alpha",
  "status": "success",
  "decision": "PASS",
  "verdict": "PASS",
  "confidence": 0.96,
  "explanation": "All applicable visual preparation checks are supported by the available evidence.",
  "checks": {
    "polybag_present_sealed":   {"verdict": "PASS", "applicable": false, "detail": "Polybag not required by work order."},
    "suffocation_warning":     {"verdict": "PASS", "applicable": false, "detail": "Suffocation warning not required."},
    "fnsku_label_placement":    {"verdict": "PASS", "applicable": true,  "detail": "FNSKU is flat, clear of seams & edges."},
    "original_barcode_covered": {"verdict": "PASS", "applicable": true,  "detail": "Original manufacturer barcode obscured."},
    "expiry_date":              {"verdict": "PASS", "applicable": false, "detail": "Expiry date verification not required."},
    "handling_marks":           {"verdict": "PASS", "applicable": true,  "detail": "All required handling marks present."}
  },
  "evidence": {
    "image_quality": {"front_blur": 1175.01, "back_blur": 609.09, "label_blur": 1448.26, "min_blur": 609.09, "is_ambiguous": false},
    "package_bounds": [148, 75, 475, 385],
    "fnsku": {"detected": true, "placement": "flat", "box": [425, 196, 160, 115], "edge_distance_px": 38, "seam_overlap_iou": 0.0}
  },
  "record": {
    "record_id": "PRP-0001",
    "unit_id": "UNIT-0001",
    "org_id": "org_demo_alpha",
    "overall_status": "PASS",
    "workflow_state": "completed",
    "calibration": {"is_calibrated": true, "front_quality": {"blur_metric": 1175.01, "glare_ratio": 0.0285}},
    "performance": {"latency_ms": 3135.22, "estimated_compute_cost_usd": 0.00015, "cost_within_economics": true},
    "captured_at": "2026-09-20T08:17:00Z"
  },
  "latency_ms": 3135.22
}"""

    resp_code_tbl = Table([[Preformatted(resp_json_str, code_pre_style)]], colWidths=[540])
    resp_code_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), CODE_BG),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(resp_code_tbl)
    story.append(Spacer(1, 4))

    # Summary of Decision Flow
    story.append(Paragraph("Orchestrator Decision Routing Matrix:", h2_style))
    routing_data = [
        [
            Paragraph("Verdict", table_header_style),
            Paragraph("Meaning", table_header_style),
            Paragraph("Downstream Orchestrator Routing Action", table_header_style)
        ],
        [
            Paragraph("<b><font color='#059669'>PASS</font></b>", table_cell_bold),
            Paragraph("All applicable checks verified compliant.", table_cell_style),
            Paragraph("Forward unit to <b>Step 03 Pack Manager</b>. Pass <code>record</code> to Step 05.", table_cell_style)
        ],
        [
            Paragraph("<b><font color='#DC2626'>FAIL</font></b>", table_cell_bold),
            Paragraph("One or more defects detected (seam overlap, missing warning, etc.).", table_cell_style),
            Paragraph("Divert physical conveyor to <b>Rework / Relabel Station</b> with itemized failure reasons.", table_cell_style)
        ],
        [
            Paragraph("<b><font color='#D97706'>UNCERTAIN</font></b>", table_cell_bold),
            Paragraph("Visual ambiguity (blur &lt; 25, glare, missing camera angle).", table_cell_style),
            Paragraph("Route to <b>Human QA Station</b> (Fail-Open guarantee). Never halt warehouse conveyors.", table_cell_style)
        ]
    ]
    rout_tbl = Table(routing_data, colWidths=[70, 190, 280])
    rout_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(rout_tbl)
    story.append(Spacer(1, 5))

    # Important Integration Notes
    story.append(Paragraph("Important Integration Notes", h1_style))
    story.append(Paragraph(
        "Orchestrator engineers must observe these 6 critical operational rules and integration behaviors:",
        body_style
    ))

    notes = [
        ("1. Multi-Tenancy Scoping (Rule 1):", 
         "Every request must supply <code>org_id</code> (or header <code>X-Org-ID</code>) matching <code>org_demo_alpha</code> or <code>org_demo_bravo</code>. Cross-tenant queries are strictly rejected with <code>403 Forbidden</code>."),
        ("2. Fail-Open Safety Wrapper (Rule 3):", 
         "If camera captures are blurry (blur score &lt; 25), glared, or missing, the agent does NOT raise 500 errors. It returns <code>UNCERTAIN</code> with <code>workflow_state: pending_review</code> so physical lines never jam."),
        ("3. Idempotency & Duplicate Prevention:", 
         "Calling <code>/run</code> multiple times for the same unit returns the cached record instantly without redundant compute. To force fresh re-inspection, supply <code>\"force_reinspect\": true</code>."),
        ("4. Downstream Interoperability (Step 05 Recovery):", 
         "The full evidence record in <code>record</code> contains calibrated photographic blur metrics, glare ratios, and pixel coordinates. The Recovery Manager (Pod 05) requires this exact structure to reverse Amazon chargebacks."),
        ("5. Latency & Batching SLAs:", 
         "Single unit evaluation latency is ~3000ms - 4000ms. For large batches (&gt;10 units), submit jobs via <code>POST /api/v1/jobs</code> and poll <code>GET /api/v1/jobs/{job_id}</code> to prevent gateway timeouts."),
        ("6. Human Overrides are Data (Honesty Rule 2):", 
         "When warehouse operators override an agent verdict, call <code>POST /api/v1/override</code>. The original verdict, operator ID, and mandatory explanation are immutably logged into the audit trail.")
    ]

    for title, desc in notes:
        note_p = Paragraph(f"&bull; <b>{title}</b> {desc}", bullet_style)
        story.append(note_p)

    story.append(Spacer(1, 4))

    # Sign-off box
    signoff_data = [[
        Paragraph("<b>Integration Readiness:</b> Verified & fully compliant with CUBE 2026 Round 3 Agent I/O Contract.<br/>"
                  "<b>Technical Support:</b> Pod 02 Prep Compliance Team | Repository: <code>cube26-prp-0211-dhanvind360</code>", 
                  ParagraphStyle('SO', fontName='Helvetica', fontSize=7.5, leading=10, textColor=MUTED))
    ]]
    signoff_tbl = Table(signoff_data, colWidths=[540])
    signoff_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(signoff_tbl)

    # Build document with NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated PDF: {filename}")

if __name__ == "__main__":
    build_pdf()
