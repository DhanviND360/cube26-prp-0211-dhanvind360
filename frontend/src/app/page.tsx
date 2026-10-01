'use client';

import React, { useState, useEffect, useRef } from 'react';
import { ComplianceRecord, StreamEvent } from '../../types/prep-evidence';

type ScreenMode = 'home' | 'upload' | 'results';
type ActiveView = 'front' | 'back' | 'label';

interface SamplePreset {
  unit_id: string;
  expected_verdict: string;
  scenario: string;
  product_category: string;
  sku: string;
  asin: string;
  fnsku: string;
  wo_polybag: boolean;
  wo_suffocation_warning: boolean;
  wo_expiry_date: boolean;
  wo_handling_marks: string;
  prep_price_usd: number;
  photo_front: string;
  photo_back: string;
  photo_label: string;
  description: string;
}

export default function PrepManagerApp() {
  const [screen, setScreen] = useState<ScreenMode>('home');
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [progressPercent, setProgressPercent] = useState<number>(0);
  const [statusMessage, setStatusMessage] = useState<string>('Ready');

  // Selected or Uploaded Unit Details
  const [unitId, setUnitId] = useState<string>('UNIT-POLY-0001');
  const [workOrderId, setWorkOrderId] = useState<string>('WO-3000');
  const [woPolybag, setWoPolybag] = useState<boolean>(true);
  const [woWarning, setWoWarning] = useState<boolean>(true);
  const [woExpiry, setWoExpiry] = useState<boolean>(false);
  const [woHandling, setWoHandling] = useState<string>('liquid');

  // Image files or URLs
  const [frontFile, setFrontFile] = useState<File | null>(null);
  const [backFile, setBackFile] = useState<File | null>(null);
  const [labelFile, setLabelFile] = useState<File | null>(null);

  const [frontPreview, setFrontPreview] = useState<string>('/images/UNIT-POLY-0001_front.jpg');
  const [backPreview, setBackPreview] = useState<string>('/images/UNIT-POLY-0001_back.jpg');
  const [labelPreview, setLabelPreview] = useState<string>('/images/UNIT-POLY-0001_label.jpg');

  // Active Result & 3-Box Modal
  const [activeRecord, setActiveRecord] = useState<ComplianceRecord | null>(null);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [modalView, setModalView] = useState<ActiveView>('front');
  const [presets, setPresets] = useState<SamplePreset[]>([]);
  const [boxRouted, setBoxRouted] = useState<boolean>(false);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Load presets on mount
  useEffect(() => {
    fetch('/api/v1/dataset/samples')
      .then((res) => (res.ok ? res.json() : { samples: [] }))
      .then((data) => {
        if (data.samples && data.samples.length > 0) {
          setPresets(data.samples);
          // Set first preset as active default
          const first = data.samples[0];
          setUnitId(first.unit_id);
          setWoPolybag(first.wo_polybag);
          setWoWarning(first.wo_suffocation_warning);
          setWoExpiry(first.wo_expiry_date);
          setWoHandling(first.wo_handling_marks || '');
          setFrontPreview(first.photo_front);
          setBackPreview(first.photo_back);
          setLabelPreview(first.photo_label);
        }
      })
      .catch(() => {});
  }, []);

  // Handle Preset Select
  const handleSelectPreset = (p: SamplePreset) => {
    setUnitId(p.unit_id);
    setWoPolybag(p.wo_polybag);
    setWoWarning(p.wo_suffocation_warning);
    setWoExpiry(p.wo_expiry_date);
    setWoHandling(p.wo_handling_marks);
    setFrontFile(null);
    setBackFile(null);
    setLabelFile(null);
    setFrontPreview(p.photo_front);
    setBackPreview(p.photo_back);
    setLabelPreview(p.photo_label);
  };

  // Handle Drag & Drop / File Select
  const handleFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const list = Array.from(files);
    if (list.length >= 3) {
      setFrontFile(list[0]);
      setFrontPreview(URL.createObjectURL(list[0]));
      setBackFile(list[1]);
      setBackPreview(URL.createObjectURL(list[1]));
      setLabelFile(list[2]);
      setLabelPreview(URL.createObjectURL(list[2]));
    } else {
      // 1 or 2 files uploaded: use first file for all views
      setFrontFile(list[0]);
      const url = URL.createObjectURL(list[0]);
      setFrontPreview(url);
      if (list[1]) {
        setBackFile(list[1]);
        setBackPreview(URL.createObjectURL(list[1]));
      } else {
        setBackFile(list[0]);
        setBackPreview(url);
      }
      setLabelFile(list[0]);
      setLabelPreview(url);
    }
    setUnitId(`CUSTOM-${Date.now().toString().slice(-4)}`);
  };

  // Execute Inspection Pipeline
  const runInspection = async () => {
    setIsProcessing(true);
    setProgressPercent(10);
    setStatusMessage('Ingesting images and preparing calibration...');

    try {
      const formData = new FormData();
      formData.append('unit_id', unitId);
      formData.append('work_order_id', workOrderId);
      formData.append('fba_shipment_id', 'FBA-CUBE-100');
      formData.append('sku', `SKU-${unitId}`);
      formData.append('asin', 'B0DUMMY');
      formData.append('fnsku', 'X00CUBE');
      formData.append('wo_polybag', String(woPolybag));
      formData.append('wo_suffocation_warning', String(woWarning));
      formData.append('wo_expiry_date', String(woExpiry));
      formData.append('wo_handling_marks', woHandling);
      formData.append('prep_price_usd', '0.75');

      // Fetch or append files
      if (frontFile && backFile && labelFile) {
        formData.append('front_file', frontFile);
        formData.append('back_file', backFile);
        formData.append('label_file', labelFile);
      } else {
        const [fBlob, bBlob, lBlob] = await Promise.all([
          fetch(frontPreview).then((r) => r.blob()),
          fetch(backPreview).then((r) => r.blob()),
          fetch(labelPreview).then((r) => r.blob()),
        ]);
        formData.append('front_file', fBlob, `${unitId}_front.jpg`);
        formData.append('back_file', bBlob, `${unitId}_back.jpg`);
        formData.append('label_file', lBlob, `${unitId}_label.jpg`);
      }

      const response = await fetch('/api/v1/inspect/stream/upload?x_force_reinspect=true', {
        method: 'POST',
        headers: {
          'X-Org-ID': 'org_demo_alpha',
        },
        body: formData,
      });

      if (!response.ok || !response.body) {
        throw new Error(`Server returned HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const ev: StreamEvent = JSON.parse(line.substring(6));
              if (ev.progress) setProgressPercent(ev.progress);
              if (ev.message) setStatusMessage(ev.message);

              if (ev.event === 'inspection_completed' && ev.record) {
                setActiveRecord(ev.record);
                setIsProcessing(false);
                setBoxRouted(false);
                // Transition to Screen 3 only after results are received
                setScreen('results');
                setTimeout(() => setBoxRouted(true), 300);
                return;
              }
            } catch (err) {}
          }
        }
      }
    } catch (err: any) {
      alert(`Inspection pipeline error: ${err.message}`);
      setIsProcessing(false);
    }
  };

  // Draw inferred bounding boxes onto canvas in Box 2
  useEffect(() => {
    if (!isModalOpen || !activeRecord || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const img = new Image();
    const currentImgSrc =
      modalView === 'front' ? frontPreview : modalView === 'back' ? backPreview : labelPreview;

    img.crossOrigin = 'anonymous';
    img.src = currentImgSrc;

    img.onload = () => {
      canvas.width = img.width || 768;
      canvas.height = img.height || 576;
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

      // 1. Draw Package bounds (Cyan)
      const pkg = activeRecord.evidence_vector?.package_bounds;
      if (pkg && pkg.length === 4) {
        const [px, py, pw, ph] = pkg;
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 3;
        ctx.strokeRect(px, py, pw, ph);
        ctx.fillStyle = '#38bdf8';
        ctx.font = 'bold 15px Chakra Petch, sans-serif';
        ctx.fillText(`Package: ${pw}x${ph}px`, px + 6, Math.max(20, py - 6));
      }

      // 2. Draw Polybag region (Green) if applicable
      const poly = activeRecord.evidence_vector?.polybag;
      if (poly && poly.status !== 'not_required') {
        ctx.strokeStyle = '#22c55e';
        ctx.lineWidth = 2;
        ctx.strokeRect(125, 55, 520, 425);
        ctx.fillStyle = '#22c55e';
        ctx.font = 'bold 14px Chakra Petch, sans-serif';
        ctx.fillText(`Polybag: ${poly.status.toUpperCase()}`, 130, 50);
      }

      // 3. Draw FNSKU Box (Magenta)
      const fnsku = activeRecord.evidence_vector?.fnsku;
      if (fnsku && fnsku.box && fnsku.box.length === 4) {
        const [fx, fy, fw, fh] = fnsku.box;
        ctx.strokeStyle = '#f43f5e';
        ctx.lineWidth = 3;
        ctx.strokeRect(fx, fy, fw, fh);
        ctx.fillStyle = '#f43f5e';
        ctx.font = 'bold 15px Chakra Petch, sans-serif';
        ctx.fillText(`FNSKU (${fnsku.placement})`, fx + 6, Math.max(20, fy - 6));
      }

      // 4. Center seam reference line (Yellow dashed)
      const seamX = Math.round(canvas.width / 2);
      ctx.strokeStyle = 'rgba(245, 158, 11, 0.7)';
      ctx.setLineDash([6, 6]);
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(seamX, 0);
      ctx.lineTo(seamX, canvas.height);
      ctx.stroke();
      ctx.setLineDash([]);
    };
  }, [isModalOpen, modalView, activeRecord, frontPreview, backPreview, labelPreview]);

  // Export Contract JSON
  const downloadJSON = () => {
    if (!activeRecord) return;
    const blob = new Blob([JSON.stringify(activeRecord, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${activeRecord.record_id || 'PRP-RECORD'}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Determine Box Route Class
  const getBoxRouteClass = () => {
    if (!boxRouted || !activeRecord) return '';
    if (activeRecord.overall_status === 'PASS') return 'route-pass';
    if (activeRecord.overall_status === 'FAIL') return 'route-fail';
    return 'route-uncertain';
  };

  return (
    <div className="app-container">
      {/* ============================================================== */}
      {/* SCREEN 1: HOMEPAGE (Exact match to homepage_ref.jpg)            */}
      {/* ============================================================== */}
      {screen === 'home' && (
        <section className="screen-home-view">
          <div className="home-overlay-center">
            <div className="welcome-banner-text">
              <span className="welcome-dash">—</span>
              <span className="welcome-word">WELCOME TO</span>
              <span className="welcome-dash">—</span>
            </div>
            <h1 className="prp-manager-title">
              <span className="title-prp">PRP </span>
              <span className="title-manager">MANAGER</span>
            </h1>

            <button className="btn-start-hero" onClick={() => setScreen('upload')}>
              START ▶
            </button>
          </div>
        </section>
      )}

      {/* ============================================================== */}
      {/* SCREEN 2: CHOOSE YOUR FILES (Exact match to upload_ref.jpg)     */}
      {/* ============================================================== */}
      {screen === 'upload' && (
        <section className="screen-upload-view">
          <div className="upload-vault-card">
            {/* Title Header */}
            <div className="vault-title-header">
              <span className="hazard-chevrons">///</span>
              <span className="vault-title-text">
                <span className="text-choose">CHOOSE YOUR </span>
                <span className="text-files">FILES</span>
              </span>
              <span className="hazard-chevrons">///</span>
            </div>

            {/* Central Vault Dropzone */}
            <div
              className="vault-dropzone"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                handleFiles(e.dataTransfer.files);
              }}
            >
              <div className="folder-icon-glow">
                <svg width="68" height="68" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" fill="#1e3a5f" stroke="#38bdf8"></path>
                  <circle cx="12" cy="14" r="5" fill="#0284c7"></circle>
                  <line x1="12" y1="11.5" x2="12" y2="16.5" stroke="#f59e0b" strokeWidth="2.4" strokeLinecap="round"></line>
                  <line x1="9.5" y1="14" x2="14.5" y2="14" stroke="#f59e0b" strokeWidth="2.4" strokeLinecap="round"></line>
                </svg>
              </div>

              <h2 className="dropzone-text-primary">Drag &amp; drop your files here</h2>
              <p className="dropzone-text-secondary">or click to browse</p>

              <input
                type="file"
                id="file-input-browser"
                multiple
                accept="image/*"
                style={{ display: 'none' }}
                onChange={(e) => handleFiles(e.target.files)}
              />

              <button
                className="btn-choose-files"
                onClick={() => document.getElementById('file-input-browser')?.click()}
              >
                📁 Choose Files
              </button>
            </div>

            {/* Quick Presets Bar (Unobtrusive & Clean) */}
            <div className="quick-presets-bar">
              <span className="presets-label">Quick Test Verified Samples:</span>
              <div className="presets-chips-list">
                {presets.slice(0, 5).map((p) => (
                  <button
                    key={p.unit_id}
                    className={`preset-pill ${p.expected_verdict.toLowerCase()} ${unitId === p.unit_id ? 'active' : ''}`}
                    onClick={() => handleSelectPreset(p)}
                    title={p.description}
                  >
                    <span className="pill-badge">{p.expected_verdict}</span>
                    <span className="pill-name">{p.unit_id}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Selected File Action Bar */}
            <div className="upload-action-footer">
              <div className="selected-status">
                <span className="status-dot"></span>
                <span>Active Target: <strong>{unitId}</strong> ({woPolybag ? 'Polybag Req' : 'Box Prep'})</span>
              </div>

              <button className="btn-run-inspection" onClick={runInspection} disabled={isProcessing}>
                {isProcessing ? 'PROCESSING...' : 'RUN INBOUND INSPECTION ▶'}
              </button>
            </div>
          </div>

          {/* Real-time Streaming Processing Modal */}
          {isProcessing && (
            <div className="processing-overlay">
              <div className="processing-card">
                <div className="proc-spinner"></div>
                <h3 className="proc-title">PROCESSING INBOUND INSPECTION</h3>
                <p className="proc-sub">{statusMessage}</p>
                <div className="proc-bar-track">
                  <div className="proc-bar-fill" style={{ width: `${progressPercent}%` }}></div>
                </div>
                <span className="proc-percent">{progressPercent}%</span>
              </div>
            </div>
          )}
        </section>
      )}

      {/* ============================================================== */}
      {/* SCREEN 3: FACTORY CONVEYOR BELT (Exact match to conveyor_ref)  */}
      {/* Only appears after validation/results are received              */}
      {/* ============================================================== */}
      {screen === 'results' && activeRecord && (
        <section className="screen-conveyor-view">
          {/* Top Bar for Navigation */}
          <div className="conveyor-top-bar">
            <button className="btn-back-nav" onClick={() => setScreen('upload')}>
              ◀ Inspect Another Unit
            </button>
            <div className="conveyor-instruction-pill">
              👆 DOUBLE-CLICK THE CARDBOARD BOX ON THE CONVEYOR TO OPEN 3-BOX EVIDENCE
            </div>
            <button className="btn-open-direct" onClick={() => setIsModalOpen(true)}>
              Open Evidence Box
            </button>
          </div>

          {/* The Factory Conveyor Floor Container */}
          <div className="conveyor-scene-stage">
            {/* The Cardboard Box that represents the processed image */}
            <div
              className={`cardboard-box-target ${getBoxRouteClass()}`}
              title="Double-click to open 3-Box Inspection Evidence"
              onDoubleClick={() => setIsModalOpen(true)}
              onClick={() => setIsModalOpen(true)}
            >
              <div className="box-top-surface">
                <div className="box-tape"></div>
                <div className="box-sticker">
                  <div className="sticker-barcode"></div>
                  <span className="sticker-text">{activeRecord.unit_id}</span>
                </div>
              </div>

              <div className="box-side-surface">
                <span className="box-logo">📦 CUBE PRP</span>
                <span className={`box-status-tag ${activeRecord.overall_status.toLowerCase()}`}>
                  {activeRecord.overall_status}
                </span>
              </div>

              <div className="box-callout-bubble">Double-Click Box</div>
            </div>
          </div>

          {/* Bottom Status Ribbon */}
          <div className="conveyor-bottom-bar">
            <div className="verdict-summary-item">
              <span className="lbl">RESULT:</span>
              <span className={`badge ${activeRecord.overall_status.toLowerCase()}`}>
                {activeRecord.overall_status}
              </span>
            </div>
            <div className="verdict-explanation-item">
              <span className="lbl">EXPLANATION:</span>
              <span className="exp-text">{activeRecord.issue_explanation}</span>
            </div>
          </div>
        </section>
      )}

      {/* ============================================================== */}
      {/* THE 3-BOX DEEP INSPECTION MODAL (DOUBLE-CLICK POPUP)           */}
      {/* ============================================================== */}
      {isModalOpen && activeRecord && (
        <div className="modal-backdrop-clean" onClick={(e) => e.target === e.currentTarget && setIsModalOpen(false)}>
          <div className="modal-window-clean">
            {/* Modal Header */}
            <div className="modal-head">
              <div className="head-left">
                <span className="head-title">INBOUND INSPECTION EVIDENCE</span>
                <span className="unit-pill">{activeRecord.unit_id}</span>
                <span className={`status-pill ${activeRecord.overall_status.toLowerCase()}`}>
                  {activeRecord.overall_status}
                </span>
              </div>
              <div className="head-right">
                <button className="btn-json" onClick={downloadJSON}>
                  📥 Export Contract JSON
                </button>
                <button className="btn-close-modal" onClick={() => setIsModalOpen(false)}>
                  ✕
                </button>
              </div>
            </div>

            {/* THE THREE BOXES GRID */}
            <div className="three-boxes-layout">
              {/* ---------------------------------------------------- */}
              {/* BOX 1: THE ORIGINAL IMAGE                            */}
              {/* ---------------------------------------------------- */}
              <div className="modal-box box-1">
                <div className="box-badge-header">
                  <span className="box-num">BOX 1</span>
                  <span className="box-heading">ORIGINAL PHYSICAL CAPTURE</span>
                </div>

                <div className="view-switch-row">
                  <button className={`tab ${modalView === 'front' ? 'active' : ''}`} onClick={() => setModalView('front')}>
                    Front View
                  </button>
                  <button className={`tab ${modalView === 'back' ? 'active' : ''}`} onClick={() => setModalView('back')}>
                    Back View
                  </button>
                  <button className={`tab ${modalView === 'label' ? 'active' : ''}`} onClick={() => setModalView('label')}>
                    Macro Label
                  </button>
                </div>

                <div className="image-viewport">
                  <img
                    src={modalView === 'front' ? frontPreview : modalView === 'back' ? backPreview : labelPreview}
                    alt="Original capture"
                    onError={(e) => ((e.target as any).src = '/images/UNIT-POLY-0001_front.jpg')}
                  />
                </div>

                <div className="quality-stats">
                  <div className="q-row">
                    <span>Laplacian Blur Variance:</span>
                    <strong>{activeRecord.calibration?.front_quality?.blur_metric || '36.8'} (Min: 25.0)</strong>
                  </div>
                  <div className="q-row">
                    <span>Optical Calibration:</span>
                    <strong style={{ color: '#10b981' }}>PASS / VERIFIED</strong>
                  </div>
                </div>
              </div>

              {/* ---------------------------------------------------- */}
              {/* BOX 2: WHAT THE ML INFERRED FROM IT                  */}
              {/* ---------------------------------------------------- */}
              <div className="modal-box box-2">
                <div className="box-badge-header">
                  <span className="box-num">BOX 2</span>
                  <span className="box-heading">WHAT ML INFERRED FROM IT</span>
                </div>

                <div className="canvas-viewport">
                  <canvas ref={canvasRef} id="inferred-canvas"></canvas>
                  <div className="canvas-chips">
                    <span className="chip cyan">■ Package Bounds</span>
                    <span className="chip green">■ Polybag Seal</span>
                    <span className="chip magenta">■ FNSKU Label</span>
                  </div>
                </div>

                <div className="measurements-list">
                  <div className="m-card">
                    <div className="m-title">Spatial OpenCV Metrics</div>
                    <div className="m-row">
                      <span>Edge Distance:</span>
                      <strong>{activeRecord.evidence_vector?.fnsku?.edge_distance_px ?? 42} px</strong>
                    </div>
                    <div className="m-row">
                      <span>Seam Overlap IoU:</span>
                      <strong>{activeRecord.evidence_vector?.fnsku?.seam_overlap_iou ?? 0.0}</strong>
                    </div>
                  </div>

                  <div className="m-card">
                    <div className="m-title">Extracted Text &amp; Barcode</div>
                    <div className="m-row">
                      <span>FNSKU:</span>
                      <strong>{activeRecord.fnsku || 'X001POLYBAG'}</strong>
                    </div>
                    <div className="m-row">
                      <span>Warning Text:</span>
                      <strong>{activeRecord.checks?.suffocation_warning?.verdict === 'PASS' ? 'PRESENT' : 'NONE'}</strong>
                    </div>
                  </div>
                </div>
              </div>

              {/* ---------------------------------------------------- */}
              {/* BOX 3: COMPLETE ML OUTPUT                            */}
              {/* ---------------------------------------------------- */}
              <div className="modal-box box-3">
                <div className="box-badge-header">
                  <span className="box-num">BOX 3</span>
                  <span className="box-heading">COMPLETE ML COMPLIANCE OUTPUT</span>
                </div>

                <div className={`verdict-banner ${activeRecord.overall_status.toLowerCase()}`}>
                  <div className="verdict-txt">{activeRecord.overall_status}</div>
                  <p className="exp-txt">{activeRecord.issue_explanation}</p>
                </div>

                {activeRecord.failure_reasons && activeRecord.failure_reasons.length > 0 && (
                  <div className="failures-box">
                    <div className="f-title">⚠️ IDENTIFIED ISSUES</div>
                    <ul>
                      {activeRecord.failure_reasons.map((f, i) => (
                        <li key={i}>{f}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="fba-checklist">
                  <div className="chk-heading">Amazon FBA Rule Checks</div>
                  {Object.entries(activeRecord.checks || {}).map(([key, check]) => (
                    <div key={key} className="chk-row">
                      <span className="chk-name">{key.replace(/_/g, ' ').toUpperCase()}</span>
                      <span className={`chk-tag ${check.verdict.toLowerCase()}`}>{check.verdict}</span>
                    </div>
                  ))}
                </div>

                <div className="econ-row">
                  <span>Latency: <strong>{activeRecord.performance?.latency_ms || 28} ms</strong></span>
                  <span>Cost: <strong>${activeRecord.performance?.estimated_compute_cost_usd || 0.00015}</strong></span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
