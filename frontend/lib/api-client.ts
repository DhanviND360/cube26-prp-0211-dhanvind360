/**
 * API Client Library for Next.js / Vercel frontend.
 * Provides:
 * - Real-time SSE streaming inspection (upload -> sequential image events -> completed record)
 * - Standard REST CRUD operations
 * - Multi-tenancy header enforcement (X-Org-ID)
 */

import {
  ComplianceRecord,
  WorkOrderInput,
  StreamEvent,
  OverridePayload
} from '../types/prep-evidence';

export class PrepManagerApiClient {
  private baseUrl: string;
  private orgId: string;
  private apiKey?: string;

  constructor(options?: { baseUrl?: string; orgId?: string; apiKey?: string }) {
    this.baseUrl = options?.baseUrl || process.env.NEXT_PUBLIC_PREP_API_URL || 'http://localhost:8000';
    this.orgId = options?.orgId || process.env.NEXT_PUBLIC_DEFAULT_ORG_ID || 'org_demo_alpha';
    this.apiKey = options?.apiKey || process.env.NEXT_PUBLIC_PREP_API_KEY;
  }

  public setTenant(orgId: string) {
    this.orgId = orgId;
  }

  private getHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Org-ID': this.orgId
    };
    if (this.apiKey) {
      headers['X-API-Key'] = this.apiKey;
    }
    return headers;
  }

  /**
   * Streams progressive inspection events via Server-Sent Events (SSE).
   * Calls onEvent as each image perspective completes analysis.
   */
  public async streamInspection(
    input: WorkOrderInput,
    onEvent: (event: StreamEvent) => void,
    onError?: (error: Error) => void
  ): Promise<ComplianceRecord | null> {
    try {
      const response = await fetch(`${this.baseUrl}/api/v1/inspect/stream`, {
        method: 'POST',
        headers: this.getHeaders(),
        body: JSON.stringify(input)
      });

      if (!response.ok) {
        throw new Error(`Inspection failed with HTTP ${response.status}: ${await response.text()}`);
      }

      if (!response.body) {
        throw new Error('ReadableStream not supported by browser environment.');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let finalRecord: ComplianceRecord | null = null;
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6).trim();
            if (dataStr) {
              try {
                const event: StreamEvent = JSON.parse(dataStr);
                onEvent(event);
                if (event.event === 'inspection_completed' && event.record) {
                  finalRecord = event.record;
                }
              } catch (e) {
                console.warn('Failed to parse SSE payload:', dataStr);
              }
            }
          }
        }
      }
      return finalRecord;
    } catch (err: any) {
      if (onError) onError(err);
      throw err;
    }
  }

  /**
   * Synchronous single-call inspection.
   */
  public async inspectUnit(input: WorkOrderInput): Promise<ComplianceRecord> {
    const res = await fetch(`${this.baseUrl}/api/v1/inspect`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(input)
    });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${await res.text()}`);
    }
    return res.json();
  }

  /**
   * Multipart photo upload inspection.
   */
  public async inspectWithUpload(
    metadata: WorkOrderInput,
    frontFile: File | Blob,
    backFile: File | Blob,
    labelFile: File | Blob
  ): Promise<ComplianceRecord> {
    const formData = new FormData();
    formData.append('unit_id', metadata.unit_id);
    formData.append('work_order_id', metadata.work_order_id || 'WO-3000');
    formData.append('fba_shipment_id', metadata.fba_shipment_id || 'FBA-CUBE-100');
    formData.append('sku', metadata.sku || 'SKU-SAMPLE');
    formData.append('asin', metadata.asin || 'B0DUMMY');
    formData.append('fnsku', metadata.fnsku || 'X00CUBE');
    formData.append('wo_polybag', String(Boolean(metadata.wo_polybag)));
    formData.append('wo_suffocation_warning', String(Boolean(metadata.wo_suffocation_warning)));
    formData.append('wo_expiry_date', String(Boolean(metadata.wo_expiry_date)));
    formData.append('wo_handling_marks', metadata.wo_handling_marks || '');
    formData.append('prep_price_usd', String(metadata.prep_price_usd || 0.75));

    formData.append('front_file', frontFile);
    formData.append('back_file', backFile);
    formData.append('label_file', labelFile);

    const headers: Record<string, string> = {
      'X-Org-ID': this.orgId
    };
    if (this.apiKey) headers['X-API-Key'] = this.apiKey;

    const res = await fetch(`${this.baseUrl}/api/v1/inspect/upload`, {
      method: 'POST',
      headers,
      body: formData
    });
    if (!res.ok) {
      throw new Error(`Upload failed: ${await res.text()}`);
    }
    return res.json();
  }

  /**
   * Retrieve records scoped to the active tenant.
   */
  public async listRecords(limit = 50, offset = 0): Promise<{ count: number; records: ComplianceRecord[] }> {
    const res = await fetch(`${this.baseUrl}/api/v1/records?limit=${limit}&offset=${offset}`, {
      headers: this.getHeaders()
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  /**
   * Retrieve a specific unit record.
   */
  public async getRecord(unitId: string): Promise<ComplianceRecord> {
    const res = await fetch(`${this.baseUrl}/api/v1/records/${unitId}`, {
      headers: this.getHeaders()
    });
    if (!res.ok) throw new Error(`Unit ${unitId} not found.`);
    return res.json();
  }

  /**
   * Record a human operator override (Honesty Rule 2).
   */
  public async submitOverride(override: OverridePayload): Promise<any> {
    const res = await fetch(`${this.baseUrl}/api/v1/override`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(override)
    });
    if (!res.ok) throw new Error(`Override failed: ${await res.text()}`);
    return res.json();
  }

  /**
   * Health check probe.
   */
  public async checkHealth(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/health`);
    return res.json();
  }
}

export const prepApiClient = new PrepManagerApiClient();
