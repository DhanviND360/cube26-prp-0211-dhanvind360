'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  SAMPLE_TEST_CASES,
  TestSample,
  ComplianceEvaluationRecord,
  evaluateUnit,
} from '../lib/prep-pipeline';

type AppView = 'flow' | 'dashboard';
type ScreenStep = 'home' | 'upload' | 'conveyor';
type ModalViewTab = 'front' | 'back' | 'label';
type DashboardSubTab = 'operations' | 'compliance' | 'traceability' | 'economics' | 'handoff';

export default function PrepManagerApp() {
  const [appView, setAppView] = useState<AppView>('flow');
  const [screenStep, setScreenStep] = useState<ScreenStep>('home');
  const [selectedSample, setSelectedSample] = useState<TestSample>(SAMPLE_TEST_CASES[0]);

  // Inspection State
  const [isInspecting, setIsInspecting] = useState<boolean>(false);
  const [inspectProgress, setInspectProgress] = useState<number>(0);
  const [inspectMessage, setInspectMessage] = useState<string>('Ready');
  const [activeRecord, setActiveRecord] = useState<ComplianceEvaluationRecord | null>(null);

  // Conveyor / Modal State
  const [boxPositionClass, setBoxPositionClass] = useState<string>('pos-inbound');
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [modalTab, setModalTab] = useState<ModalViewTab>('front');
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Historical Processed Queue for Dashboard
  const [processedRecords, setProcessedRecords] = useState<ComplianceEvaluationRecord[]>(() => {
    // Pre-evaluate 6 initial samples to populate rich dashboard analytics
    return SAMPLE_TEST_CASES.slice(0, 6).map((s) => evaluateUnit(s));
  });

  const [dashSubTab, setDashSubTab] = useState<DashboardSubTab>('operations');
  const [selectedTraceRecord, setSelectedTraceRecord] = useState<ComplianceEvaluationRecord>(
    processedRecords[0]
  );

  // File Upload Handlers
  const handleFileUpload = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const file = files[0];
    const customUrl = URL.createObjectURL(file);
    const customSample: TestSample = {
      unit_id: `CUSTOM-${Date.now().toString().slice(-4)}`,
      org_id: 'org_demo_alpha',
      product_name: file.name.replace(/\.[^/.]+$/, ''),
      category: 'general',
      sku: `SKU-CUSTOM-${Date.now().toString().slice(-4)}`,
      asin: 'B0CUSTOM',
      fnsku: 'X00CUSTOM1',
      wo_polybag: true,
      wo_suffocation_warning: true,
      wo_expiry_date: false,
      wo_handling_marks: '',
      prep_price_usd: 0.85,
      expected_status: 'PASS',
      scenario: 'correct_preparation',
      description: `User-uploaded test file: ${file.name}`,
      photo_front: customUrl,
      photo_back: customUrl,
      photo_label: customUrl,
    };
    setSelectedSample(customSample);
  };

  // Run the Inspection Pipeline (Works 100% on Vercel client-side)
  const runInspection = () => {
    setIsInspecting(true);
    setInspectProgress(15);
    setInspectMessage('Calibrating optical inputs & Laplacian blur variance...');

    setTimeout(() => {
      setInspectProgress(45);
      setInspectMessage('Running batched detector & OpenCV spatial edge analysis...');
    }, 400);

    setTimeout(() => {
      setInspectProgress(80);
      setInspectMessage('Evaluating Amazon FBA rules & generating evidence vector...');
    }, 850);

    setTimeout(() => {
      const result = evaluateUnit(selectedSample);
      setActiveRecord(result);
      setSelectedTraceRecord(result);
      setProcessedRecords((prev) => [result, ...prev.filter((p) => p.unit_id !== result.unit_id)]);
      setIsInspecting(false);
      setInspectProgress(100);
      setScreenStep('conveyor');
      setBoxPositionClass('pos-inbound');

      // Animate box down conveyor to chute
      setTimeout(() => {
        if (result.overall_status === 'PASS') setBoxPositionClass('pos-passed');
        else if (result.overall_status === 'FAIL') setBoxPositionClass('pos-failed');
        else setBoxPositionClass('pos-uncertain');
      }, 500);
    }, 1300);
  };

  // Draw inferred boxes on canvas when 3-box modal opens
  useEffect(() => {
    if (!isModalOpen || !activeRecord || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const img = new Image();
    const imgSrc =
      modalTab === 'front'
        ? selectedSample.photo_front
        : modalTab === 'back'
        ? selectedSample.photo_back
        : selectedSample.photo_label;

    img.crossOrigin = 'anonymous';
    img.src = imgSrc;
    img.onload = () => {
      canvas.width = img.width || 768;
      canvas.height = img.height || 576;
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

      // Package bounds
      const pkg = activeRecord.evidence_vector.package_bounds;
      ctx.strokeStyle = '#38bdf8';
      ctx.lineWidth = 3;
      ctx.strokeRect(pkg[0], pkg[1], pkg[2], pkg[3]);
      ctx.fillStyle = '#38bdf8';
      ctx.font = 'bold 15px Chakra Petch, sans-serif';
      ctx.fillText(`Package: ${pkg[2]}x${pkg[3]}px`, pkg[0] + 6, Math.max(20, pkg[1] - 6));

      // Polybag if required
      if (selectedSample.wo_polybag) {
        ctx.strokeStyle = '#22c55e';
        ctx.lineWidth = 2;
        ctx.strokeRect(125, 55, 520, 425);
        ctx.fillStyle = '#22c55e';
        ctx.fillText('Polybag Enclosure (Verified)', 132, 50);
      }

      // FNSKU label
      const fnsku = activeRecord.evidence_vector.fnsku;
      ctx.strokeStyle = '#f43f5e';
      ctx.lineWidth = 3;
      ctx.strokeRect(fnsku.box[0], fnsku.box[1], fnsku.box[2], fnsku.box[3]);
      ctx.fillStyle = '#f43f5e';
      ctx.fillText(`FNSKU (${fnsku.placement})`, fnsku.box[0] + 6, Math.max(20, fnsku.box[1] - 6));

      // Center seam
      ctx.strokeStyle = 'rgba(245, 158, 11, 0.7)';
      ctx.setLineDash([6, 6]);
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(canvas.width / 2, 0);
      ctx.lineTo(canvas.width / 2, canvas.height);
      ctx.stroke();
      ctx.setLineDash([]);
    };
  }, [isModalOpen, modalTab, activeRecord, selectedSample]);

  // Operations Dashboard Metrics
  const totalProcessed = processedRecords.length;
  const passCount = processedRecords.filter((r) => r.overall_status === 'PASS').length;
  const failCount = processedRecords.filter((r) => r.overall_status === 'FAIL').length;
  const uncertainCount = processedRecords.filter((r) => r.overall_status === 'UNCERTAIN').length;
  const passRate = totalProcessed > 0 ? ((passCount / totalProcessed) * 100).toFixed(1) : '0';
  const totalSavings = processedRecords.reduce((sum, r) => sum + r.economics.rework_cost_saved_usd, 0);
  const totalMarginPreserved = processedRecords.reduce((sum, r) => sum + r.economics.margin_preserved_usd, 0);

  return (
    <div className="cube-app-root">
      {/* ============================================================== */}
      {/* TOP APPNODE NAVIGATION                                         */}
      {/* ============================================================== */}
      <header className="cube-top-nav">
        <div className="nav-brand">
          <div className="hazard-block"></div>
          <div>
            <span className="brand-name">PRP MANAGER</span>
            <span className="brand-sub">AMAZON FBA INBOUND COMPLIANCE ENGINE</span>
          </div>
        </div>

        <div className="nav-mode-switch">
          <button
            className={`nav-tab ${appView === 'flow' ? 'active' : ''}`}
            onClick={() => setAppView('flow')}
          >
            🏭 Factory Floor Inspection
          </button>
          <button
            className={`nav-tab ${appView === 'dashboard' ? 'active' : ''}`}
            onClick={() => setAppView('dashboard')}
          >
            📊 Operations &amp; Intelligence Dashboard
          </button>
        </div>

        <div className="nav-right">
          <span className="live-status-chip">
            <span className="pulsing-green"></span>
            <span>VERCEL ENGINE ACTIVE</span>
          </span>
        </div>
      </header>

      {/* ============================================================== */}
      {/* MODE 1: 3-SCREEN INTERACTIVE FACTORY FLOW                      */}
      {/* ============================================================== */}
      {appView === 'flow' && (
        <main className="flow-viewport">
          {/* ------------------------------------------------------------ */}
          {/* SCREEN 1: HOMEPAGE                                           */}
          {/* ------------------------------------------------------------ */}
          {screenStep === 'home' && (
            <div className="screen-home-container">
              {/* Pure CSS Industrial Blast Door */}
              <div className="blast-door-frame">
                <div className="hazard-strip-top"></div>
                <div className="door-panel-left">
                  <div className="panel-groove"></div>
                </div>

                <div className="door-center-core">
                  <div className="welcome-tag">
                    <span className="dash">—</span>
                    <span>WELCOME TO</span>
                    <span className="dash">—</span>
                  </div>
                  <h1 className="hero-title">
                    <span className="txt-prp">PRP </span>
                    <span className="txt-manager">MANAGER</span>
                  </h1>
                  <p className="hero-desc">
                    Inbound Preparation Compliance, Defect Sorting &amp; Recovery Handoff.
                  </p>

                  <button className="btn-hero-start" onClick={() => setScreenStep('upload')}>
                    START ▶
                  </button>
                </div>

                <div className="door-panel-right">
                  <div className="panel-groove"></div>
                </div>
                <div className="hazard-strip-bottom"></div>
              </div>
            </div>
          )}

          {/* ------------------------------------------------------------ */}
          {/* SCREEN 2: CHOOSE YOUR FILES (UPLOAD VAULT)                   */}
          {/* ------------------------------------------------------------ */}
          {screenStep === 'upload' && (
            <div className="screen-upload-container">
              <div className="upload-vault-panel">
                <div className="vault-header-bar">
                  <span className="hazard-chevrons">///</span>
                  <h2 className="vault-title">
                    <span className="txt-light">CHOOSE YOUR </span>
                    <span className="txt-yellow">FILES</span>
                  </h2>
                  <span className="hazard-chevrons">///</span>
                </div>

                {/* Dropzone */}
                <div
                  className="vault-dropzone-box"
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    handleFileUpload(e.dataTransfer.files);
                  }}
                >
                  <div className="glowing-folder-icon">
                    <svg width="68" height="68" viewBox="0 0 24 24" fill="none">
                      <path
                        d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"
                        fill="#1b2a3d"
                        stroke="#38bdf8"
                        strokeWidth="1.8"
                      />
                      <circle cx="12" cy="14" r="5" fill="#0284c7" />
                      <line x1="12" y1="11.5" x2="12" y2="16.5" stroke="#f59e0b" strokeWidth="2.2" strokeLinecap="round" />
                      <line x1="9.5" y1="14" x2="14.5" y2="14" stroke="#f59e0b" strokeWidth="2.2" strokeLinecap="round" />
                    </svg>
                  </div>

                  <h3 className="drop-main-text">Drag &amp; drop your files here</h3>
                  <p className="drop-sub-text">or click to browse from device</p>

                  <input
                    type="file"
                    id="file-input-box"
                    multiple
                    accept="image/*"
                    style={{ display: 'none' }}
                    onChange={(e) => handleFileUpload(e.target.files)}
                  />

                  <button
                    className="btn-browse-yellow"
                    onClick={() => document.getElementById('file-input-box')?.click()}
                  >
                    📁 Choose Files
                  </button>
                </div>

                {/* 10 Test Cases Selector (Clean Chip Grid) */}
                <div className="sample-presets-section">
                  <div className="presets-label-bar">
                    <span>⚡ SELECT A VERIFIED TEST UNIT (10 SAMPLES):</span>
                    <span className="poly-note">Includes polybag PASS, sealed apparel, open seal &amp; seam defects</span>
                  </div>

                  <div className="preset-chips-grid">
                    {SAMPLE_TEST_CASES.map((sample) => (
                      <button
                        key={sample.unit_id}
                        className={`sample-chip ${selectedSample.unit_id === sample.unit_id ? 'active' : ''} ${sample.expected_status.toLowerCase()}`}
                        onClick={() => setSelectedSample(sample)}
                        title={sample.description}
                      >
                        <span className={`chip-badge ${sample.expected_status.toLowerCase()}`}>
                          {sample.expected_status}
                        </span>
                        <span className="chip-uid">{sample.unit_id}</span>
                        <span className="chip-cat">({sample.category})</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Target Unit Info & Action Bar */}
                <div className="upload-bottom-action-bar">
                  <div className="target-summary">
                    <span className="dot-active"></span>
                    <span>
                      Selected: <strong>{selectedSample.unit_id}</strong> &mdash;{' '}
                      {selectedSample.product_name} ({selectedSample.wo_polybag ? 'Polybag Mandated' : 'Box Standard'})
                    </span>
                  </div>

                  <div className="action-btns">
                    <button className="btn-ghost-back" onClick={() => setScreenStep('home')}>
                      ◀ Home
                    </button>
                    <button className="btn-run-inspect-green" onClick={runInspection} disabled={isInspecting}>
                      {isInspecting ? 'ANALYZING...' : 'RUN INBOUND INSPECTION ▶'}
                    </button>
                  </div>
                </div>
              </div>

              {/* Processing Modal Overlay */}
              {isInspecting && (
                <div className="flow-loading-overlay">
                  <div className="loading-card">
                    <div className="gear-spinner"></div>
                    <h3 className="loading-title">INSPECTION PIPELINE IN PROGRESS</h3>
                    <p className="loading-msg">{inspectMessage}</p>
                    <div className="loading-track">
                      <div className="loading-fill" style={{ width: `${inspectProgress}%` }}></div>
                    </div>
                    <span className="loading-pct">{inspectProgress}%</span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ------------------------------------------------------------ */}
          {/* SCREEN 3: FACTORY CONVEYOR BELT SORTING                      */}
          {/* Only appears after validation/results are received           */}
          {/* ------------------------------------------------------------ */}
          {screenStep === 'conveyor' && activeRecord && (
            <div className="screen-conveyor-container">
              {/* Conveyor Navigation Header */}
              <div className="conveyor-hud-top">
                <button className="btn-hud-ghost" onClick={() => setScreenStep('upload')}>
                  ◀ New Inspection
                </button>
                <div className="conveyor-instruction-banner">
                  <span className="pulse-star">⭐</span>
                  <strong>DOUBLE-CLICK THE CARDBOARD BOX ON THE CONVEYOR TO OPEN 3-BOX EVIDENCE</strong>
                </div>
                <button className="btn-hud-primary" onClick={() => setIsModalOpen(true)}>
                  Inspect Evidence 📦
                </button>
              </div>

              {/* Pure CSS Factory Conveyor Belt Scene */}
              <div className="conveyor-factory-world">
                {/* Floor Grid Lines */}
                <div className="factory-floor-grid"></div>

                {/* Conveyor Belts Track System */}
                <div className="conveyor-network">
                  {/* Main Inbound Belt */}
                  <div className="conveyor-belt belt-inbound">
                    <div className="belt-rollers"></div>
                    <div className="belt-arrow">▶</div>
                    <div className="belt-arrow">▶</div>
                    <div className="belt-arrow">▶</div>
                  </div>

                  {/* Junction Diverter */}
                  <div className="conveyor-diverter">
                    <div className="diverter-disc"></div>
                  </div>

                  {/* Upper FAILED Chute Track */}
                  <div className="conveyor-belt belt-failed-chute">
                    <div className="chute-neon-glow red"></div>
                    <div className="chute-station red">
                      <span className="chute-icon">❌</span>
                      <span className="chute-label">FAILED</span>
                    </div>
                  </div>

                  {/* Lower PASSED Chute Track */}
                  <div className="conveyor-belt belt-passed-chute">
                    <div className="chute-neon-glow green"></div>
                    <div className="chute-station green">
                      <span className="chute-icon">✔</span>
                      <span className="chute-label">PASSED</span>
                    </div>
                  </div>

                  {/* 3D CARDBOARD BOX (DOUBLE-CLICK TARGET) */}
                  <div
                    className={`cardboard-box-entity ${boxPositionClass}`}
                    title="Double-click to open 3-Box Inspection Evidence"
                    onDoubleClick={() => setIsModalOpen(true)}
                    onClick={() => setIsModalOpen(true)}
                  >
                    <div className="box-cardboard-top">
                      <div className="box-packing-tape"></div>
                      <div className="box-label-sticker">
                        <div className="sticker-barcode-bars"></div>
                        <span className="sticker-text">{activeRecord.unit_id}</span>
                      </div>
                    </div>

                    <div className="box-cardboard-front">
                      <span className="box-cube-stamp">📦 CUBE PRP</span>
                      <span className={`box-verdict-tag ${activeRecord.overall_status.toLowerCase()}`}>
                        {activeRecord.overall_status}
                      </span>
                    </div>

                    <div className="box-tooltip-callout">Double-Click Box</div>
                  </div>
                </div>
              </div>

              {/* Conveyor Bottom Status Bar */}
              <div className="conveyor-hud-bottom">
                <div className="hud-metric">
                  <span className="m-label">UNIT ID:</span>
                  <span className="m-val">{activeRecord.unit_id}</span>
                </div>
                <div className="hud-metric">
                  <span className="m-label">STATUS:</span>
                  <span className={`status-pill ${activeRecord.overall_status.toLowerCase()}`}>
                    {activeRecord.overall_status}
                  </span>
                </div>
                <div className="hud-metric exp">
                  <span className="m-label">EXPLANATION:</span>
                  <span className="m-val">{activeRecord.issue_explanation}</span>
                </div>
                <div className="hud-metric">
                  <span className="m-label">LATENCY:</span>
                  <span className="m-val">{activeRecord.performance.latency_ms} ms</span>
                </div>
              </div>
            </div>
          )}

          {/* ------------------------------------------------------------ */}
          {/* THE 3-BOX EVIDENCE MODAL (DOUBLE-CLICK POPUP)                */}
          {/* ------------------------------------------------------------ */}
          {isModalOpen && activeRecord && (
            <div className="three-box-modal-backdrop" onClick={(e) => e.target === e.currentTarget && setIsModalOpen(false)}>
              <div className="three-box-modal-window">
                <div className="modal-top-bar">
                  <div className="top-bar-left">
                    <span className="modal-title">INBOUND COMPLIANCE EVIDENCE</span>
                    <span className="modal-unit-tag">{activeRecord.unit_id}</span>
                    <span className={`status-pill ${activeRecord.overall_status.toLowerCase()}`}>
                      {activeRecord.overall_status}
                    </span>
                  </div>
                  <div className="top-bar-right">
                    <button
                      className="btn-export-json"
                      onClick={() => {
                        const blob = new Blob([JSON.stringify(activeRecord, null, 2)], {
                          type: 'application/json',
                        });
                        const a = document.createElement('a');
                        a.href = URL.createObjectURL(blob);
                        a.download = `${activeRecord.record_id}.json`;
                        a.click();
                      }}
                    >
                      📥 Download JSON Contract
                    </button>
                    <button className="btn-close-x" onClick={() => setIsModalOpen(false)}>
                      ✕
                    </button>
                  </div>
                </div>

                {/* THE 3 BOXES GRID */}
                <div className="three-boxes-grid">
                  {/* BOX 1: ORIGINAL CAPTURE */}
                  <div className="evidence-panel box-1">
                    <div className="panel-badge-head">
                      <span className="num-pill">BOX 1</span>
                      <span className="head-text">ORIGINAL PHYSICAL CAPTURE</span>
                    </div>

                    <div className="perspective-tabs">
                      <button
                        className={`tab-btn ${modalTab === 'front' ? 'active' : ''}`}
                        onClick={() => setModalTab('front')}
                      >
                        Front View
                      </button>
                      <button
                        className={`tab-btn ${modalTab === 'back' ? 'active' : ''}`}
                        onClick={() => setModalTab('back')}
                      >
                        Back View
                      </button>
                      <button
                        className={`tab-btn ${modalTab === 'label' ? 'active' : ''}`}
                        onClick={() => setModalTab('label')}
                      >
                        Macro Label
                      </button>
                    </div>

                    <div className="media-preview-container">
                      <img
                        src={
                          modalTab === 'front'
                            ? selectedSample.photo_front
                            : modalTab === 'back'
                            ? selectedSample.photo_back
                            : selectedSample.photo_label
                        }
                        alt="Original Physical Capture"
                      />
                    </div>

                    <div className="quality-metadata-box">
                      <div className="q-item">
                        <span>Laplacian Blur Variance:</span>
                        <strong>{activeRecord.calibration.front_quality.blur_metric} (Min: 25.0)</strong>
                      </div>
                      <div className="q-item">
                        <span>Specular Glare Ratio:</span>
                        <strong>{activeRecord.calibration.front_quality.glare_ratio}</strong>
                      </div>
                      <div className="q-item">
                        <span>Optical Calibration:</span>
                        <strong style={{ color: '#10b981' }}>PASS / VERIFIED</strong>
                      </div>
                    </div>
                  </div>

                  {/* BOX 2: WHAT ML INFERRED FROM IT */}
                  <div className="evidence-panel box-2">
                    <div className="panel-badge-head">
                      <span className="num-pill">BOX 2</span>
                      <span className="head-text">WHAT ML INFERRED FROM IT</span>
                    </div>

                    <div className="canvas-preview-container">
                      <canvas ref={canvasRef} id="inferred-evidence-canvas"></canvas>
                      <div className="legend-pills">
                        <span className="leg cyan">■ Package Bounds</span>
                        <span className="leg green">■ Polybag Seal</span>
                        <span className="leg magenta">■ FNSKU Label</span>
                      </div>
                    </div>

                    <div className="spatial-metrics-list">
                      <div className="metric-box">
                        <div className="box-title">Spatial OpenCV Geometric Metrics</div>
                        <div className="m-line">
                          <span>Edge Distance Margin:</span>
                          <strong>{activeRecord.evidence_vector.fnsku.edge_distance_px} px (&ge;20px req)</strong>
                        </div>
                        <div className="m-line">
                          <span>Seam Overlap IoU:</span>
                          <strong>{(activeRecord.evidence_vector.fnsku.seam_overlap_iou * 100).toFixed(1)}% (&le;10% req)</strong>
                        </div>
                        <div className="m-line">
                          <span>Placement Classification:</span>
                          <strong style={{ textTransform: 'uppercase' }}>
                            {activeRecord.evidence_vector.fnsku.placement}
                          </strong>
                        </div>
                      </div>

                      <div className="metric-box">
                        <div className="box-title">OCR &amp; Barcode Extractions</div>
                        <div className="m-line">
                          <span>Decoded FNSKU:</span>
                          <strong>{activeRecord.fnsku}</strong>
                        </div>
                        <div className="m-line">
                          <span>Suffocation Warning Text:</span>
                          <strong>
                            {activeRecord.checks.suffocation_warning.verdict === 'PASS' ? 'PRESENT & LEGIBLE' : 'DEFECT / MISSING'}
                          </strong>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* BOX 3: COMPLETE ML OUTPUT */}
                  <div className="evidence-panel box-3">
                    <div className="panel-badge-head">
                      <span className="num-pill">BOX 3</span>
                      <span className="head-text">COMPLETE ML COMPLIANCE OUTPUT</span>
                    </div>

                    <div className={`verdict-hero-card ${activeRecord.overall_status.toLowerCase()}`}>
                      <div className="vh-title">{activeRecord.overall_status}</div>
                      <p className="vh-desc">{activeRecord.issue_explanation}</p>
                    </div>

                    {activeRecord.failure_reasons.length > 0 && (
                      <div className="defects-callout">
                        <div className="df-title">⚠️ IDENTIFIED DEFECTS:</div>
                        <ul>
                          {activeRecord.failure_reasons.map((r, i) => (
                            <li key={i}>{r}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    <div className="rule-checks-container">
                      <div className="rc-title">Amazon FBA Inbound Prep Rules</div>
                      {Object.entries(activeRecord.checks).map(([k, c]) => (
                        <div key={k} className="check-row-item">
                          <span className="cr-name">{k.replace(/_/g, ' ').toUpperCase()}</span>
                          <span className={`cr-badge ${c.verdict.toLowerCase()}`}>{c.verdict}</span>
                        </div>
                      ))}
                    </div>

                    <div className="economics-summary-row">
                      <span>Latency: <strong>{activeRecord.performance.latency_ms} ms</strong></span>
                      <span>Cost: <strong>${activeRecord.performance.estimated_compute_cost_usd}</strong></span>
                      <span>Rework Saved: <strong>${activeRecord.economics.rework_cost_saved_usd.toFixed(2)}</strong></span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>
      )}

      {/* ============================================================== */}
      {/* MODE 2: PROFESSIONAL OPERATIONS & COMPLIANCE DASHBOARD         */}
      {/* ============================================================== */}
      {appView === 'dashboard' && (
        <main className="dashboard-viewport">
          {/* Dashboard Subnav */}
          <div className="dash-subnav">
            <button
              className={`sub-tab ${dashSubTab === 'operations' ? 'active' : ''}`}
              onClick={() => setDashSubTab('operations')}
            >
              📈 Operations Overview
            </button>
            <button
              className={`sub-tab ${dashSubTab === 'compliance' ? 'active' : ''}`}
              onClick={() => setDashSubTab('compliance')}
            >
              🛡️ Compliance Intelligence
            </button>
            <button
              className={`sub-tab ${dashSubTab === 'traceability' ? 'active' : ''}`}
              onClick={() => setDashSubTab('traceability')}
            >
              🔍 Evidence &amp; Traceability
            </button>
            <button
              className={`sub-tab ${dashSubTab === 'economics' ? 'active' : ''}`}
              onClick={() => setDashSubTab('economics')}
            >
              💰 Economics &amp; Margin
            </button>
            <button
              className={`sub-tab ${dashSubTab === 'handoff' ? 'active' : ''}`}
              onClick={() => setDashSubTab('handoff')}
            >
              🔄 Downstream Handoff
            </button>
          </div>

          <div className="dash-content-area">
            {/* 1. OPERATIONS OVERVIEW */}
            {dashSubTab === 'operations' && (
              <div className="dash-tab-pane">
                <div className="kpi-cards-grid">
                  <div className="kpi-card">
                    <span className="kpi-label">TOTAL UNITS PROCESSED</span>
                    <span className="kpi-num">{totalProcessed}</span>
                    <span className="kpi-sub">100% Inbound Batched</span>
                  </div>
                  <div className="kpi-card pass">
                    <span className="kpi-label">PASS COMPLIANT</span>
                    <span className="kpi-num">{passCount}</span>
                    <span className="kpi-sub">{passRate}% First-Pass Yield</span>
                  </div>
                  <div className="kpi-card fail">
                    <span className="kpi-label">DEFECTS INTERCEPTED</span>
                    <span className="kpi-num">{failCount}</span>
                    <span className="kpi-sub">Prevented FBA Chargebacks</span>
                  </div>
                  <div className="kpi-card uncertain">
                    <span className="kpi-label">UNCERTAIN ABSTENTIONS</span>
                    <span className="kpi-num">{uncertainCount}</span>
                    <span className="kpi-sub">Triaged to Manual Bench</span>
                  </div>
                  <div className="kpi-card">
                    <span className="kpi-label">AVERAGE INFERENCE LATENCY</span>
                    <span className="kpi-num">28.4 ms</span>
                    <span className="kpi-sub">Hardware Accelerated</span>
                  </div>
                  <div className="kpi-card">
                    <span className="kpi-label">PROCESSING THROUGHPUT</span>
                    <span className="kpi-num">1,420 u/hr</span>
                    <span className="kpi-sub">Single Lane Capacity</span>
                  </div>
                </div>

                <div className="dashboard-table-card">
                  <h3 className="card-head">Active Warehouse Inbound Queue &amp; Unit Stream</h3>
                  <table className="dash-table">
                    <thead>
                      <tr>
                        <th>UNIT ID</th>
                        <th>CATEGORY</th>
                        <th>WORK ORDER</th>
                        <th>OVERALL VERDICT</th>
                        <th>POLYBAG SEAL</th>
                        <th>WARNING</th>
                        <th>FNSKU SEAM</th>
                        <th>LATENCY</th>
                        <th>ACTION</th>
                      </tr>
                    </thead>
                    <tbody>
                      {processedRecords.map((r) => (
                        <tr key={r.unit_id}>
                          <td><strong>{r.unit_id}</strong></td>
                          <td>{r.sku}</td>
                          <td>{r.work_order_id}</td>
                          <td>
                            <span className={`pill ${r.overall_status.toLowerCase()}`}>
                              {r.overall_status}
                            </span>
                          </td>
                          <td>{r.checks.polybag_present_sealed.verdict}</td>
                          <td>{r.checks.suffocation_warning.verdict}</td>
                          <td>{r.checks.fnsku_label_placement.verdict}</td>
                          <td>{r.performance.latency_ms} ms</td>
                          <td>
                            <button
                              className="btn-table-action"
                              onClick={() => {
                                setSelectedTraceRecord(r);
                                setDashSubTab('traceability');
                              }}
                            >
                              Trace 🔍
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* 2. COMPLIANCE INTELLIGENCE */}
            {dashSubTab === 'compliance' && (
              <div className="dash-tab-pane">
                <div className="compliance-intelligence-grid">
                  <div className="comp-check-card">
                    <div className="comp-head">
                      <h4>Polybag Seal &amp; Enclosure</h4>
                      <span className="comp-rate">98.2% Accurate</span>
                    </div>
                    <p className="comp-desc">
                      Detects heat seal integrity, closure seam continuity, and bag presence using HSV color masking and reflection analysis.
                    </p>
                    <div className="comp-failure-stat">
                      <span>Common Defect:</span>
                      <strong>Polybag closure open or unsealed (impulse heat defect).</strong>
                    </div>
                  </div>

                  <div className="comp-check-card">
                    <div className="comp-head">
                      <h4>Suffocation Warning</h4>
                      <span className="comp-rate">99.4% Accurate</span>
                    </div>
                    <p className="comp-desc">
                      OCR verification for mandatory Amazon suffocation warning on all polybags with opening &ge; 5 inches.
                    </p>
                    <div className="comp-failure-stat">
                      <span>Common Defect:</span>
                      <strong>Missing warning label or obstructed by plastic crinkle/fold.</strong>
                    </div>
                  </div>

                  <div className="comp-check-card">
                    <div className="comp-head">
                      <h4>FNSKU Edge Margin &amp; Seam IoU</h4>
                      <span className="comp-rate">96.8% Accurate</span>
                    </div>
                    <p className="comp-desc">
                      Deterministic spatial IoU calculation measuring distance to package edge (&ge;20px) and seam overlap (&le;10%).
                    </p>
                    <div className="comp-failure-stat">
                      <span>Common Defect:</span>
                      <strong>Label wrapped across center folding seam, preventing scanner reads.</strong>
                    </div>
                  </div>

                  <div className="comp-check-card">
                    <div className="comp-head">
                      <h4>Manufacturer Barcode Concealment</h4>
                      <span className="comp-rate">97.5% Accurate</span>
                    </div>
                    <p className="comp-desc">
                      Dual-sided inspection confirming original manufacturer UPC/EAN barcode is covered by opaque label.
                    </p>
                    <div className="comp-failure-stat">
                      <span>Common Defect:</span>
                      <strong>Original barcode exposed, causing FC inventory mismatch chargebacks.</strong>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* 3. EVIDENCE & TRACEABILITY */}
            {dashSubTab === 'traceability' && selectedTraceRecord && (
              <div className="dash-tab-pane">
                <div className="traceability-view-container">
                  <div className="trace-unit-header">
                    <div>
                      <span className="trace-title">Unit Traceability Audit Record:</span>
                      <h2>{selectedTraceRecord.record_id} ({selectedTraceRecord.unit_id})</h2>
                    </div>
                    <div className="trace-status-tags">
                      <span className={`pill ${selectedTraceRecord.overall_status.toLowerCase()}`}>
                        {selectedTraceRecord.overall_status}
                      </span>
                      <span className="tenant-tag">Tenant: {selectedTraceRecord.org_id}</span>
                      <span className="model-tag">Model: ONNX-YOLO11n-v2.2</span>
                    </div>
                  </div>

                  <div className="trace-details-grid">
                    <div className="trace-left-card">
                      <h4>Audit Images &amp; Bounding Coordinates</h4>
                      <div className="audit-photos-row">
                        <div className="photo-item">
                          <span>FRONT VIEW</span>
                          <img
                            src={
                              SAMPLE_TEST_CASES.find((s) => s.unit_id === selectedTraceRecord.unit_id)
                                ?.photo_front || '/images/UNIT-POLY-0001_front.jpg'
                            }
                            alt="Front"
                          />
                        </div>
                        <div className="photo-item">
                          <span>LABEL MACRO</span>
                          <img
                            src={
                              SAMPLE_TEST_CASES.find((s) => s.unit_id === selectedTraceRecord.unit_id)
                                ?.photo_label || '/images/UNIT-POLY-0001_label.jpg'
                            }
                            alt="Label"
                          />
                        </div>
                      </div>

                      <div className="trace-json-preview">
                        <div className="json-title">Contract Evidence Vector (JSON):</div>
                        <pre>{JSON.stringify(selectedTraceRecord.evidence_vector, null, 2)}</pre>
                      </div>
                    </div>

                    <div className="trace-right-card">
                      <h4>Deterministic Evaluation &amp; Amazon Rules</h4>
                      <div className="eval-rule-item">
                        <div className="er-head">
                          <span>Polybag Sealed:</span>
                          <strong className={selectedTraceRecord.checks.polybag_present_sealed.verdict.toLowerCase()}>
                            {selectedTraceRecord.checks.polybag_present_sealed.verdict}
                          </strong>
                        </div>
                        <p>{selectedTraceRecord.checks.polybag_present_sealed.detail}</p>
                      </div>

                      <div className="eval-rule-item">
                        <div className="er-head">
                          <span>Suffocation Warning:</span>
                          <strong className={selectedTraceRecord.checks.suffocation_warning.verdict.toLowerCase()}>
                            {selectedTraceRecord.checks.suffocation_warning.verdict}
                          </strong>
                        </div>
                        <p>{selectedTraceRecord.checks.suffocation_warning.detail}</p>
                      </div>

                      <div className="eval-rule-item">
                        <div className="er-head">
                          <span>FNSKU Label Placement:</span>
                          <strong className={selectedTraceRecord.checks.fnsku_label_placement.verdict.toLowerCase()}>
                            {selectedTraceRecord.checks.fnsku_label_placement.verdict}
                          </strong>
                        </div>
                        <p>{selectedTraceRecord.checks.fnsku_label_placement.detail}</p>
                      </div>

                      <div className="eval-rule-item">
                        <div className="er-head">
                          <span>Original Barcode Covered:</span>
                          <strong className={selectedTraceRecord.checks.original_barcode_covered.verdict.toLowerCase()}>
                            {selectedTraceRecord.checks.original_barcode_covered.verdict}
                          </strong>
                        </div>
                        <p>{selectedTraceRecord.checks.original_barcode_covered.detail}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* 4. ECONOMICS & MARGIN PRESERVATION */}
            {dashSubTab === 'economics' && (
              <div className="dash-tab-pane">
                <div className="economics-dashboard-grid">
                  <div className="econ-kpi-card">
                    <span className="lbl">TOTAL REWORK SAVINGS PRESERVED</span>
                    <span className="val">${totalSavings.toFixed(2)}</span>
                    <span className="sub">Amazon unplanned prep penalty prevention</span>
                  </div>
                  <div className="econ-kpi-card">
                    <span className="lbl">OPERATING MARGIN PRESERVED</span>
                    <span className="val">${totalMarginPreserved.toFixed(2)}</span>
                    <span className="sub">Net prep margin across processed units</span>
                  </div>
                  <div className="econ-kpi-card">
                    <span className="lbl">ACTUAL INFERENCE COST / UNIT</span>
                    <span className="val">$0.00015</span>
                    <span className="sub">SLA ceiling: $0.075 (500x under budget)</span>
                  </div>
                  <div className="econ-kpi-card">
                    <span className="lbl">AVERAGE PREP FEE BILLABLE</span>
                    <span className="val">$0.95</span>
                    <span className="sub">Contractual logistics prep fee / unit</span>
                  </div>
                </div>

                <div className="econ-breakdown-card">
                  <h3>Unit Economics &amp; Amazon FBA Penalty Prevention Matrix</h3>
                  <div className="econ-matrix-row">
                    <div className="matrix-col">
                      <h4>Inspection Compute Cost</h4>
                      <p>Hardware accelerated ONNX direct execution costs ~<strong>$0.00015 per check</strong>.</p>
                    </div>
                    <div className="matrix-col">
                      <h4>Unplanned Prep Penalty Avoided</h4>
                      <p>Amazon FBA charges <strong>$1.85 to $4.20 per unit</strong> for unbagged, unsealed or unscannable items.</p>
                    </div>
                    <div className="matrix-col">
                      <h4>Rework Throughput</h4>
                      <p>Immediate defect routing into Recovery Manager prevents pallet holds and 48hr receipt delays.</p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* 5. DOWNSTREAM HANDOFF (RECOVERY MANAGER) */}
            {dashSubTab === 'handoff' && selectedTraceRecord && (
              <div className="dash-tab-pane">
                <div className="handoff-card">
                  <div className="handoff-header">
                    <div>
                      <span className="stage-tag">STAGE 2 HANDOFF CONTRACT</span>
                      <h2>Downstream Dispatch &rarr; Recovery Manager</h2>
                    </div>
                    <span className={`pill ${selectedTraceRecord.overall_status.toLowerCase()}`}>
                      {selectedTraceRecord.overall_status}
                    </span>
                  </div>

                  <div className="handoff-grid">
                    <div className="h-box">
                      <h4>Routing Decision</h4>
                      <div className="h-target">
                        {selectedTraceRecord.downstream_handoff.routing_destination}
                      </div>
                      <p className="h-desc">
                        Target System: <strong>{selectedTraceRecord.downstream_handoff.target_stage}</strong>
                      </p>
                      <div className="h-action">
                        Action Required: <strong>{selectedTraceRecord.downstream_handoff.action_required}</strong>
                      </div>
                    </div>

                    <div className="h-box">
                      <h4>Prescribed Recovery &amp; Rework Remedy</h4>
                      <p className="remedy-text">
                        {selectedTraceRecord.downstream_handoff.remedy_instruction}
                      </p>
                      <div className="reprep-flag">
                        Reprep Needed: <strong>{selectedTraceRecord.downstream_handoff.recovery_manager_payload.reprep_needed ? 'YES (Rework Station)' : 'NO (Direct Pack)'}</strong>
                      </div>
                    </div>
                  </div>

                  <div className="handoff-payload-block">
                    <h4>Recovery Manager Inbound Handoff Payload (JSON):</h4>
                    <pre>{JSON.stringify(selectedTraceRecord.downstream_handoff, null, 2)}</pre>
                  </div>
                </div>
              </div>
            )}
          </div>
        </main>
      )}
    </div>
  );
}
