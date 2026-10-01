/**
 * TypeScript API Contracts & Types for CUBE Prep Manager (Pod 02).
 * Conforms strictly to the cross-pod evidence contract:
 * prep_evidence_contract.json
 */

export type OverallVerdict = 'PASS' | 'FAIL' | 'UNCERTAIN';

export type CheckStatus = 'PASS' | 'FAIL' | 'UNCERTAIN' | 'NOT_REQUIRED';

export type WorkflowState = 'completed' | 'pending_review' | 'overridden';

export interface CheckResult {
  verdict: CheckStatus;
  applicable: boolean;
  detail: string;
}

export interface EvidenceRegion {
  view: 'front' | 'back' | 'label';
  label: string;
  bbox: [number, number, number, number]; // [x, y, width, height]
  measurement?: {
    edge_distance_px?: number;
    seam_overlap_iou?: number;
    curvature?: number;
    [key: string]: any;
  };
}

export interface CalibrationReport {
  is_calibrated: boolean;
  front_quality?: {
    blur_metric: number;
    glare_ratio: number;
    mean_brightness: number;
    resolution: [number, number];
  };
  back_quality?: any;
  label_quality?: any;
}

export interface PerformanceMetrics {
  latency_ms: number;
  estimated_compute_cost_usd: number;
  target_max_check_cost_usd?: number;
  cost_within_economics: boolean;
  total_streaming_latency_ms?: number;
}

export interface ComplianceRecord {
  record_id: string; // e.g. PRP-0001
  unit_id: string;   // e.g. UNIT-0001
  org_id: string;    // org_demo_alpha or org_demo_bravo (Rule 1)
  work_order_id: string;
  fba_shipment_id: string;
  sku: string;
  asin: string;
  fnsku: string;
  overall_status: OverallVerdict;
  workflow_state: WorkflowState;
  issue_explanation: string;
  failure_reasons: string[];
  uncertain_reasons: string[];
  checks: {
    polybag_present_sealed: CheckResult;
    suffocation_warning: CheckResult;
    fnsku_label_placement: CheckResult;
    original_barcode_covered: CheckResult;
    expiry_date: CheckResult;
    handling_marks: CheckResult;
  };
  evidence_regions: EvidenceRegion[];
  evidence_vector: Record<string, any>;
  calibration: CalibrationReport;
  performance: PerformanceMetrics;
  operator_id?: string;
  captured_at: string;
}

export interface StreamEvent {
  event: 'job_started' | 'front_completed' | 'back_completed' | 'label_completed' | 'inspection_completed' | 'error';
  progress: number;
  unit_id?: string;
  org_id?: string;
  view?: 'front' | 'back' | 'label';
  summary?: Record<string, any>;
  message: string;
  record?: ComplianceRecord;
  timestamp: number;
}

export interface WorkOrderInput {
  unit_id: string;
  work_order_id?: string;
  fba_shipment_id?: string;
  sku?: string;
  asin?: string;
  fnsku?: string;
  wo_polybag?: boolean;
  wo_suffocation_warning?: boolean;
  wo_expiry_date?: boolean;
  wo_handling_marks?: string;
  prep_price_usd?: number;
  front_image_ref?: string;
  back_image_ref?: string;
  label_image_ref?: string;
}

export interface OverridePayload {
  unit_id: string;
  original_verdict: OverallVerdict;
  new_verdict: OverallVerdict;
  reason: string;
  operator_id: string;
}
