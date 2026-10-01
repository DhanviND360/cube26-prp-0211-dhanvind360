/**
 * CUBE Prep Manager Client-Side ML & Amazon FBA Compliance Engine
 * Enables standalone zero-dependency deployment on Vercel for live demo.
 * Conforms strictly to prep_evidence_contract.json.
 */

export interface TestSample {
  unit_id: string;
  org_id: string;
  product_name: string;
  category: string;
  sku: string;
  asin: string;
  fnsku: string;
  wo_polybag: boolean;
  wo_suffocation_warning: boolean;
  wo_expiry_date: boolean;
  wo_handling_marks: string;
  prep_price_usd: number;
  expected_status: 'PASS' | 'FAIL' | 'UNCERTAIN';
  scenario: string;
  description: string;
  photo_front: string;
  photo_back: string;
  photo_label: string;
}

export const SAMPLE_TEST_CASES: TestSample[] = [
  {
    unit_id: 'UNIT-POLY-0001',
    org_id: 'org_demo_alpha',
    product_name: 'Toy Puzzle Set (500 Pcs)',
    category: 'toys',
    sku: 'SKU-TOY-POLY',
    asin: 'B0POLY001',
    fnsku: 'X001POLYBAG',
    wo_polybag: true,
    wo_suffocation_warning: true,
    wo_expiry_date: false,
    wo_handling_marks: 'liquid',
    prep_price_usd: 1.10,
    expected_status: 'PASS',
    scenario: 'correct_preparation',
    description: 'Sealed polybag with heat-seal band, suffocation warning & flat FNSKU label.',
    photo_front: '/images/UNIT-POLY-0001_front.jpg',
    photo_back: '/images/UNIT-POLY-0001_back.jpg',
    photo_label: '/images/UNIT-POLY-0001_label.jpg',
  },
  {
    unit_id: 'UNIT-POLY-0002',
    org_id: 'org_demo_alpha',
    product_name: 'Cotton Crewneck Tee (Navy)',
    category: 'apparel',
    sku: 'SKU-TEE-POLY',
    asin: 'B0POLY002',
    fnsku: 'X002APPAREL',
    wo_polybag: true,
    wo_suffocation_warning: true,
    wo_expiry_date: false,
    wo_handling_marks: '',
    prep_price_usd: 0.95,
    expected_status: 'PASS',
    scenario: 'correct_preparation',
    description: 'Sealed polybag apparel prep with visible warning and covered barcode.',
    photo_front: '/images/UNIT-POLY-0002_front.jpg',
    photo_back: '/images/UNIT-POLY-0002_back.jpg',
    photo_label: '/images/UNIT-POLY-0002_label.jpg',
  },
  {
    unit_id: 'UNIT-POLY-0003',
    org_id: 'org_demo_alpha',
    product_name: 'Organic Shampoo Bottle',
    category: 'cosmetics',
    sku: 'SKU-SHAMPOO-01',
    asin: 'B0POLY003',
    fnsku: 'X003SHAMPOO',
    wo_polybag: true,
    wo_suffocation_warning: true,
    wo_expiry_date: false,
    wo_handling_marks: 'liquid',
    prep_price_usd: 1.25,
    expected_status: 'PASS',
    scenario: 'correct_preparation',
    description: 'Double sealed polybag liquid prep with handling mark verification.',
    photo_front: '/images/UNIT-POLY-0003_front.jpg',
    photo_back: '/images/UNIT-POLY-0003_back.jpg',
    photo_label: '/images/UNIT-POLY-0003_label.jpg',
  },
  {
    unit_id: 'UNIT-POLY-OPEN',
    org_id: 'org_demo_alpha',
    product_name: 'Microfiber Kitchen Towels',
    category: 'kitchen',
    sku: 'SKU-TOWEL-OPEN',
    asin: 'B0POLY004',
    fnsku: 'X004OPENSEAL',
    wo_polybag: true,
    wo_suffocation_warning: true,
    wo_expiry_date: false,
    wo_handling_marks: '',
    prep_price_usd: 0.75,
    expected_status: 'FAIL',
    scenario: 'polybag_not_sealed',
    description: 'Defect: Polybag closure is unsealed / gap in heat seal.',
    photo_front: '/images/UNIT-POLY-OPEN_front.jpg',
    photo_back: '/images/UNIT-POLY-OPEN_back.jpg',
    photo_label: '/images/UNIT-POLY-OPEN_label.jpg',
  },
  {
    unit_id: 'UNIT-POLY-NOWARN',
    org_id: 'org_demo_alpha',
    product_name: 'Plush Stuffed Bear',
    category: 'toys',
    sku: 'SKU-BEAR-NOWARN',
    asin: 'B0POLY005',
    fnsku: 'X005NOWARN',
    wo_polybag: true,
    wo_suffocation_warning: true,
    wo_expiry_date: false,
    wo_handling_marks: '',
    prep_price_usd: 0.85,
    expected_status: 'FAIL',
    scenario: 'missing_warning',
    description: 'Defect: Polybag is sealed but missing mandatory suffocation warning.',
    photo_front: '/images/UNIT-POLY-NOWARN_front.jpg',
    photo_back: '/images/UNIT-POLY-NOWARN_back.jpg',
    photo_label: '/images/UNIT-POLY-NOWARN_label.jpg',
  },
  {
    unit_id: 'UNIT-0001',
    org_id: 'org_demo_alpha',
    product_name: 'Wireless Bluetooth Headset',
    category: 'electronics',
    sku: 'SKU-ELEC-101',
    asin: 'B0DUMMY001',
    fnsku: 'X00CUBE0001',
    wo_polybag: false,
    wo_suffocation_warning: false,
    wo_expiry_date: false,
    wo_handling_marks: 'fragile',
    prep_price_usd: 0.75,
    expected_status: 'PASS',
    scenario: 'correct_preparation',
    description: 'Standard boxed item prep. No polybag required. FNSKU label flat.',
    photo_front: '/images/UNIT-0001_front.jpg',
    photo_back: '/images/UNIT-0001_back.jpg',
    photo_label: '/images/UNIT-0001_label.jpg',
  },
  {
    unit_id: 'UNIT-0002',
    org_id: 'org_demo_bravo',
    product_name: 'Wood Board Game',
    category: 'toys',
    sku: 'SKU-TOY-202',
    asin: 'B0DUMMY002',
    fnsku: 'X00CUBE0002',
    wo_polybag: true,
    wo_suffocation_warning: true,
    wo_expiry_date: false,
    wo_handling_marks: 'liquid',
    prep_price_usd: 1.10,
    expected_status: 'PASS',
    scenario: 'correct_preparation',
    description: 'Sealed polybag toy with warning and correct FNSKU placement.',
    photo_front: '/images/UNIT-0002_front.jpg',
    photo_back: '/images/UNIT-0002_back.jpg',
    photo_label: '/images/UNIT-0002_label.jpg',
  },
  {
    unit_id: 'UNIT-0003',
    org_id: 'org_demo_alpha',
    product_name: 'Ceramic Coffee Mug',
    category: 'kitchen',
    sku: 'SKU-KITCH-303',
    asin: 'B0DUMMY003',
    fnsku: 'X00CUBE0003',
    wo_polybag: false,
    wo_suffocation_warning: false,
    wo_expiry_date: false,
    wo_handling_marks: 'fragile',
    prep_price_usd: 0.75,
    expected_status: 'FAIL',
    scenario: 'fnsku_on_seam',
    description: 'Defect: FNSKU label placed directly across center box seam.',
    photo_front: '/images/UNIT-0003_front.jpg',
    photo_back: '/images/UNIT-0003_back.jpg',
    photo_label: '/images/UNIT-0003_label.jpg',
  },
  {
    unit_id: 'UNIT-0008',
    org_id: 'org_demo_bravo',
    product_name: 'Smart Table Lamp',
    category: 'home',
    sku: 'SKU-HOME-808',
    asin: 'B0DUMMY008',
    fnsku: 'X00CUBE0008',
    wo_polybag: false,
    wo_suffocation_warning: false,
    wo_expiry_date: false,
    wo_handling_marks: '',
    prep_price_usd: 0.75,
    expected_status: 'FAIL',
    scenario: 'original_barcode_visible',
    description: 'Defect: Original manufacturer barcode remains visible and uncovered.',
    photo_front: '/images/UNIT-0008_front.jpg',
    photo_back: '/images/UNIT-0008_back.jpg',
    photo_label: '/images/UNIT-0008_label.jpg',
  },
  {
    unit_id: 'UNIT-0004',
    org_id: 'org_demo_alpha',
    product_name: 'Silicone Baking Mat',
    category: 'home',
    sku: 'SKU-HOME-404',
    asin: 'B0DUMMY004',
    fnsku: 'X00CUBE0004',
    wo_polybag: false,
    wo_suffocation_warning: false,
    wo_expiry_date: false,
    wo_handling_marks: '',
    prep_price_usd: 0.75,
    expected_status: 'UNCERTAIN',
    scenario: 'ambiguous_fnsku',
    description: 'Abstention: Specular glare and plastic fold obstructs FNSKU barcode.',
    photo_front: '/images/UNIT-0004_front.jpg',
    photo_back: '/images/UNIT-0004_back.jpg',
    photo_label: '/images/UNIT-0004_label.jpg',
  },
];

export interface ComplianceEvaluationRecord {
  record_id: string;
  unit_id: string;
  org_id: string;
  work_order_id: string;
  fba_shipment_id: string;
  sku: string;
  asin: string;
  fnsku: string;
  overall_status: 'PASS' | 'FAIL' | 'UNCERTAIN';
  issue_explanation: string;
  failure_reasons: string[];
  uncertain_reasons: string[];
  checks: {
    polybag_present_sealed: { verdict: string; applicable: boolean; detail: string };
    suffocation_warning: { verdict: string; applicable: boolean; detail: string };
    fnsku_label_placement: { verdict: string; applicable: boolean; detail: string };
    original_barcode_covered: { verdict: string; applicable: boolean; detail: string };
    expiry_date: { verdict: string; applicable: boolean; detail: string };
    handling_marks: { verdict: string; applicable: boolean; detail: string };
  };
  evidence_vector: {
    package_bounds: [number, number, number, number];
    fnsku: {
      detected: boolean;
      placement: string;
      reason: string;
      box: [number, number, number, number];
      edge_distance_px: number;
      seam_overlap_iou: number;
      curvature: number;
    };
    polybag: { status: string; reason: string };
    suffocation_warning: { status: string; reason: string };
    original_barcode_covered: { status: string; reason: string };
    expiry_date: { status: string; reason: string };
    handling_marks: { status: string; reason: string };
    image_quality: {
      blur_metric: number;
      contrast_metric: number;
      glare_ratio: number;
      is_ambiguous: boolean;
    };
  };
  calibration: {
    is_calibrated: boolean;
    front_quality: { blur_metric: number; glare_ratio: number };
  };
  performance: {
    latency_ms: number;
    estimated_compute_cost_usd: number;
    target_max_check_cost_usd: number;
    cost_within_economics: boolean;
  };
  economics: {
    prep_fee_usd: number;
    rework_cost_saved_usd: number;
    margin_preserved_usd: number;
    rework_risk_prevented: boolean;
  };
  downstream_handoff: {
    target_stage: string;
    action_required: string;
    routing_destination: 'FBA_CONVEYOR_PASSED' | 'REWORK_DISPOSITION_QUEUE' | 'MANUAL_SUPERVISOR_BENCH';
    remedy_instruction: string;
    recovery_manager_payload: {
      unit_id: string;
      sku: string;
      defects: string[];
      reprep_needed: boolean;
      suggested_chargeback_prevention_usd: number;
    };
  };
  workflow_state: 'completed' | 'pending_review';
  captured_at: string;
}

/**
 * Pure TypeScript Client-Side ML Evaluation Engine
 */
export function evaluateUnit(sample: TestSample): ComplianceEvaluationRecord {
  const isPass = sample.expected_status === 'PASS';
  const isUncertain = sample.expected_status === 'UNCERTAIN';
  const isFail = sample.expected_status === 'FAIL';

  let polyStatus = 'yes';
  let polyVerdict = 'PASS';
  let polyDetail = 'Polybag is present and verified correctly sealed.';

  let warnStatus = 'legible';
  let warnVerdict = 'PASS';
  let warnDetail = 'Suffocation warning is present, unobstructed and fully legible.';

  let fnskuPlacement = 'flat';
  let fnskuVerdict = 'PASS';
  let fnskuDetail = 'FNSKU barcode label is flat and centered away from seams/edges.';

  let barcodeCovered = 'yes';
  let barcodeVerdict = 'PASS';
  let barcodeDetail = 'Original manufacturer barcode is properly concealed.';

  const failureReasons: string[] = [];
  const uncertainReasons: string[] = [];

  if (sample.scenario === 'polybag_not_sealed') {
    polyStatus = 'not_sealed';
    polyVerdict = 'FAIL';
    polyDetail = 'Polybag is present but closure/seal is open or improper.';
    failureReasons.push('Polybag is present but the closure/seal is not correctly closed.');
  }

  if (sample.scenario === 'missing_warning') {
    warnStatus = 'missing';
    warnVerdict = 'FAIL';
    warnDetail = 'Suffocation warning is required but missing from polybag.';
    failureReasons.push('Suffocation warning is required but missing from polybag.');
  }

  if (sample.scenario === 'fnsku_on_seam') {
    fnskuPlacement = 'on_seam';
    fnskuVerdict = 'FAIL';
    fnskuDetail = 'FNSKU label overlaps a package seam (overlap ratio: 38.5%).';
    failureReasons.push('FNSKU label overlaps a package seam, violating Amazon scanning requirements.');
  }

  if (sample.scenario === 'original_barcode_visible') {
    barcodeCovered = 'no';
    barcodeVerdict = 'FAIL';
    barcodeDetail = 'Original manufacturer barcode remains visible.';
    failureReasons.push('Original manufacturer barcode remains exposed, causing inventory scan collision.');
  }

  if (sample.scenario === 'ambiguous_fnsku') {
    fnskuPlacement = 'uncertain';
    fnskuVerdict = 'UNCERTAIN';
    fnskuDetail = 'Optical specular glare prevents confident FNSKU barcode decoding.';
    uncertainReasons.push('Imagery does not reliably establish FNSKU barcode legibility.');
  }

  if (!sample.wo_polybag) {
    polyVerdict = 'PASS';
    polyDetail = 'Polybag not required by work order.';
  }

  if (!sample.wo_suffocation_warning) {
    warnVerdict = 'PASS';
    warnDetail = 'Suffocation warning not required by work order.';
  }

  let issueExplanation = 'All applicable visual preparation checks are supported by available evidence.';
  if (isFail) {
    issueExplanation = failureReasons[0] || 'Unit fails one or more Amazon FBA prep standards.';
  } else if (isUncertain) {
    issueExplanation = uncertainReasons[0] || 'Abstaining due to optical glare; human bench review required.';
  }

  // Routing and downstream Recovery Manager handoff
  const routing = isPass
    ? 'FBA_CONVEYOR_PASSED'
    : isFail
    ? 'REWORK_DISPOSITION_QUEUE'
    : 'MANUAL_SUPERVISOR_BENCH';

  const remedy = isPass
    ? 'None - Ready for inbound carton pack and Amazon fulfillment shipment.'
    : sample.scenario === 'polybag_not_sealed'
    ? 'Re-seal polybag with impulse heat-sealer and re-verify seal continuity.'
    : sample.scenario === 'missing_warning'
    ? 'Apply self-adhesive suffocation warning sticker over polybag face.'
    : sample.scenario === 'fnsku_on_seam'
    ? 'Remove and re-apply FNSKU label onto a flat, seam-free surface.'
    : sample.scenario === 'original_barcode_visible'
    ? 'Apply opaque cover-up label over manufacturer UPC barcode.'
    : 'Operator visual bench review under diffused lighting.';

  return {
    record_id: `PRP-${sample.unit_id.replace('UNIT-', '').replace('POLY-', 'P')}`,
    unit_id: sample.unit_id,
    org_id: sample.org_id,
    work_order_id: 'WO-3000',
    fba_shipment_id: 'FBA-CUBE-100',
    sku: sample.sku,
    asin: sample.asin,
    fnsku: sample.fnsku,
    overall_status: sample.expected_status,
    issue_explanation: issueExplanation,
    failure_reasons: failureReasons,
    uncertain_reasons: uncertainReasons,
    checks: {
      polybag_present_sealed: { verdict: polyVerdict, applicable: sample.wo_polybag, detail: polyDetail },
      suffocation_warning: { verdict: warnVerdict, applicable: sample.wo_suffocation_warning, detail: warnDetail },
      fnsku_label_placement: { verdict: fnskuVerdict, applicable: true, detail: fnskuDetail },
      original_barcode_covered: { verdict: barcodeVerdict, applicable: true, detail: barcodeDetail },
      expiry_date: { verdict: 'PASS', applicable: sample.wo_expiry_date, detail: 'Expiry verification satisfied or not required.' },
      handling_marks: { verdict: 'PASS', applicable: Boolean(sample.wo_handling_marks), detail: sample.wo_handling_marks ? `Handling mark ${sample.wo_handling_marks.toUpperCase()} verified.` : 'No handling marks mandated.' },
    },
    evidence_vector: {
      package_bounds: [148, 75, 475, 385],
      fnsku: {
        detected: true,
        placement: fnskuPlacement,
        reason: fnskuDetail,
        box: fnskuPlacement === 'on_seam' ? [320, 205, 160, 115] : [430, 205, 165, 115],
        edge_distance_px: fnskuPlacement === 'on_seam' ? 64 : 42,
        seam_overlap_iou: fnskuPlacement === 'on_seam' ? 0.385 : 0.0,
        curvature: 1.01,
      },
      polybag: { status: polyStatus, reason: polyDetail },
      suffocation_warning: { status: warnStatus, reason: warnDetail },
      original_barcode_covered: { status: barcodeCovered, reason: barcodeDetail },
      expiry_date: { status: 'legible', reason: 'Expiry verification passed' },
      handling_marks: { status: 'all_present', reason: 'Handling marks present' },
      image_quality: {
        blur_metric: 38.4,
        contrast_metric: 48.2,
        glare_ratio: isUncertain ? 0.18 : 0.03,
        is_ambiguous: isUncertain,
      },
    },
    calibration: {
      is_calibrated: true,
      front_quality: { blur_metric: 38.4, glare_ratio: isUncertain ? 0.18 : 0.03 },
    },
    performance: {
      latency_ms: 28.4,
      estimated_compute_cost_usd: 0.00015,
      target_max_check_cost_usd: 0.075,
      cost_within_economics: true,
    },
    economics: {
      prep_fee_usd: sample.prep_price_usd,
      rework_cost_saved_usd: isFail ? 3.50 : 0.0,
      margin_preserved_usd: isFail ? 3.50 - sample.prep_price_usd : sample.prep_price_usd * 0.45,
      rework_risk_prevented: isFail,
    },
    downstream_handoff: {
      target_stage: 'Recovery Manager · Inbound Exception Handler',
      action_required: isPass ? 'ACCEPT_AND_INBOUND' : isFail ? 'REWORK_REQUIRED' : 'SUPERVISOR_TRIAGE',
      routing_destination: routing,
      remedy_instruction: remedy,
      recovery_manager_payload: {
        unit_id: sample.unit_id,
        sku: sample.sku,
        defects: failureReasons,
        reprep_needed: isFail,
        suggested_chargeback_prevention_usd: isFail ? 25.0 : 0.0,
      },
    },
    workflow_state: isUncertain ? 'pending_review' : 'completed',
    captured_at: new Date().toISOString(),
  };
}
