-- ====================================================================
-- CUBE Prep Manager: Supabase PostgreSQL Schema & Multi-Tenancy (Rule 1)
-- ====================================================================

-- 1. PREP RECORDS TABLE
CREATE TABLE IF NOT EXISTS public.prep_records (
    record_id TEXT PRIMARY KEY,
    unit_id TEXT NOT NULL,
    org_id TEXT NOT NULL,
    work_order_id TEXT,
    fba_shipment_id TEXT,
    sku TEXT,
    asin TEXT,
    fnsku TEXT,
    overall_status TEXT NOT NULL CHECK (overall_status IN ('PASS', 'FAIL', 'UNCERTAIN')),
    workflow_state TEXT NOT NULL DEFAULT 'completed' CHECK (workflow_state IN ('completed', 'pending_review', 'overridden')),
    issue_explanation TEXT,
    evidence_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for lightning-fast join queries across the 5-stage chain
CREATE INDEX IF NOT EXISTS idx_prep_records_unit_id ON public.prep_records(unit_id);
CREATE INDEX IF NOT EXISTS idx_prep_records_org_id ON public.prep_records(org_id);
CREATE INDEX IF NOT EXISTS idx_prep_records_status ON public.prep_records(overall_status);

-- 2. PROGRESSIVE INSPECTION JOBS TABLE
CREATE TABLE IF NOT EXISTS public.prep_jobs (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    unit_id TEXT NOT NULL,
    org_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'processing', 'completed', 'failed')),
    progress_pct INT NOT NULL DEFAULT 0 CHECK (progress_pct BETWEEN 0 AND 100),
    current_milestone TEXT,
    work_order_payload JSONB,
    front_image_url TEXT,
    back_image_url TEXT,
    label_image_url TEXT,
    result_record JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prep_jobs_org_id ON public.prep_jobs(org_id);
CREATE INDEX IF NOT EXISTS idx_prep_jobs_unit_id ON public.prep_jobs(unit_id);

-- 3. AUDIT OVERRIDES TABLE (Honesty Rule 2)
CREATE TABLE IF NOT EXISTS public.audit_overrides (
    id BIGSERIAL PRIMARY KEY,
    unit_id TEXT NOT NULL,
    org_id TEXT NOT NULL,
    original_verdict TEXT NOT NULL CHECK (original_verdict IN ('PASS', 'FAIL', 'UNCERTAIN')),
    new_verdict TEXT NOT NULL CHECK (new_verdict IN ('PASS', 'FAIL', 'UNCERTAIN')),
    reason TEXT NOT NULL,
    operator_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_overrides_org_id ON public.audit_overrides(org_id);

-- ====================================================================
-- ROW-LEVEL SECURITY (RLS) POLICIES (ENGINEERING RULE 1)
-- ====================================================================

ALTER TABLE public.prep_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prep_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_overrides ENABLE ROW LEVEL SECURITY;

-- Prep Records RLS Policy
CREATE POLICY "Tenant isolation for prep_records" ON public.prep_records
    FOR ALL
    USING (
        org_id = COALESCE(
            current_setting('request.jwt.claim.org_id', true),
            current_setting('app.current_org_id', true),
            'org_demo_alpha'
        )
    );

-- Prep Jobs RLS Policy
CREATE POLICY "Tenant isolation for prep_jobs" ON public.prep_jobs
    FOR ALL
    USING (
        org_id = COALESCE(
            current_setting('request.jwt.claim.org_id', true),
            current_setting('app.current_org_id', true),
            'org_demo_alpha'
        )
    );

-- Audit Overrides RLS Policy
CREATE POLICY "Tenant isolation for audit_overrides" ON public.audit_overrides
    FOR ALL
    USING (
        org_id = COALESCE(
            current_setting('request.jwt.claim.org_id', true),
            current_setting('app.current_org_id', true),
            'org_demo_alpha'
        )
    );

-- ====================================================================
-- STORAGE BUCKET CONFIGURATION (SUPABASE STORAGE)
-- ====================================================================

INSERT INTO storage.buckets (id, name, public)
VALUES ('prep-evidence-images', 'prep-evidence-images', false)
ON CONFLICT (id) DO NOTHING;

-- Storage tenant isolation policy: files are stored under `{org_id}/{unit_id}_{view}.jpg`
CREATE POLICY "Tenant storage access" ON storage.objects
    FOR ALL
    USING (
        bucket_id = 'prep-evidence-images' AND
        (storage.foldername(name))[1] = COALESCE(
            current_setting('request.jwt.claim.org_id', true),
            current_setting('app.current_org_id', true),
            'org_demo_alpha'
        )
    );
