-- MR Assistant: core schema (all 21 tables).
-- Rebuilt from scratch by scripts/build_db.py; data comes from data/parquet (data-v2, frozen).
-- Conventions: IDs only in fact tables (names live in masters); timestamptz everywhere;
-- every table carries the audit columns created_at, updated_at, source_system, load_batch_id.
-- No FK on territory_id, employee_id or brand_code: those keys are not unique in their
-- source tables (geography = patch grain, employee = assignment grain, product = SKU grain).

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS btree_gist;

DROP SCHEMA IF EXISTS core CASCADE;
CREATE SCHEMA core;
SET search_path = core, public;

-- =====================================================================  reference
CREATE TABLE calendar_day (
    calendar_date        date     PRIMARY KEY,
    year                 smallint NOT NULL,
    month                smallint NOT NULL CHECK (month BETWEEN 1 AND 12),
    year_month           integer  NOT NULL,
    quarter              smallint NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    fiscal_year          text     NOT NULL,
    fiscal_quarter       smallint NOT NULL CHECK (fiscal_quarter BETWEEN 1 AND 4),
    week_of_year         smallint NOT NULL,
    day_of_week          smallint NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
    day_name             text     NOT NULL,
    is_weekend           boolean  NOT NULL,
    is_national_holiday  boolean  NOT NULL,
    holiday_name         text,
    holiday_states       text[],
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    source_system text NOT NULL DEFAULT 'app', load_batch_id text
);
CREATE INDEX ix_calendar_day_year_month ON calendar_day (year_month);

CREATE TABLE business_unit (
    business_unit_id     bigint  PRIMARY KEY,
    business_unit_name   text    NOT NULL UNIQUE,
    cluster_id           bigint  NOT NULL,
    cluster_code         text    NOT NULL,
    cluster_name         text    NOT NULL,
    calls_per_day_lower  double precision NOT NULL CHECK (calls_per_day_lower > 0),
    calls_per_day_upper  double precision NOT NULL,
    is_active            boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    source_system text NOT NULL DEFAULT 'app', load_batch_id text,
    CHECK (calls_per_day_upper >= calls_per_day_lower)
);

CREATE TABLE geography (
    patch_id          bigint  PRIMARY KEY,
    patch_name        text    NOT NULL,
    territory_id      bigint  NOT NULL,
    territory_name    text    NOT NULL,
    hq_id             bigint  NOT NULL,
    hq_name           text    NOT NULL,
    region_id         bigint  NOT NULL,
    region_name       text    NOT NULL,
    zone_id           bigint  NOT NULL,
    zone_name         text    NOT NULL,
    business_unit_id  bigint  NOT NULL REFERENCES business_unit,
    city              text    NOT NULL,
    state             text    NOT NULL,
    latitude          double precision NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude         double precision NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    is_active         boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    source_system text NOT NULL DEFAULT 'app', load_batch_id text
);
CREATE INDEX ix_geography_territory ON geography (territory_id);

CREATE TABLE employee (
    assignment_id        bigint  PRIMARY KEY,
    employee_id          bigint  NOT NULL,
    employee_code        text    NOT NULL,
    employee_name        text    NOT NULL,
    designation          text    NOT NULL CHECK (designation IN ('BO', 'ABM', 'RBM', 'ZBM')),
    business_unit_id     bigint  NOT NULL REFERENCES business_unit,
    territory_id         bigint,
    hq_id                bigint  NOT NULL,
    manager_employee_id  bigint,
    valid_from           date    NOT NULL,
    valid_to             date,
    is_current           boolean NOT NULL,
    joining_date         date    NOT NULL,
    email                text    NOT NULL,
    mobile               text    NOT NULL,
    employment_status    text    NOT NULL CHECK (employment_status IN ('active', 'resigned')),
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    source_system text NOT NULL DEFAULT 'app', load_batch_id text,
    CHECK (valid_to IS NULL OR valid_to >= valid_from),
    CHECK (is_current = (valid_to IS NULL)),
    CHECK ((designation = 'BO') = (territory_id IS NOT NULL)),
    CHECK (valid_from >= joining_date),
    CONSTRAINT ex_employee_no_overlap EXCLUDE USING gist (
        employee_id WITH =, daterange(valid_from, COALESCE(valid_to, 'infinity'::date), '[]') WITH &&)
);
CREATE UNIQUE INDEX ux_employee_current_code ON employee (employee_code) WHERE is_current;
CREATE INDEX ix_employee_employee ON employee (employee_id);
CREATE INDEX ix_employee_territory ON employee (territory_id);
CREATE INDEX ix_employee_manager ON employee (manager_employee_id);

CREATE TABLE product (
    sku_code             text          PRIMARY KEY,
    sku_name             text          NOT NULL,
    pack_size            text,
    dosage_form          text,
    brand_code           text          NOT NULL,
    brand_name           text          NOT NULL,
    manufacturer         text          NOT NULL,
    is_own_brand         boolean       NOT NULL,
    business_unit_id     bigint        REFERENCES business_unit,
    therapy_area         text          NOT NULL,
    molecule_class       text          NOT NULL,
    is_growth_brand      boolean       NOT NULL,
    is_device            boolean       NOT NULL,
    is_sample_eligible   boolean       NOT NULL,
    price_per_strip_inr  numeric(10,2) NOT NULL CHECK (price_per_strip_inr > 0),
    launch_date          date,
    is_active            boolean       NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    source_system text NOT NULL DEFAULT 'app', load_batch_id text,
    CHECK (is_own_brand = (business_unit_id IS NOT NULL))
);
CREATE INDEX ix_product_brand ON product (brand_code);

CREATE TABLE content (
    content_id          bigint  PRIMARY KEY,
    brand_code          text    NOT NULL,
    title               text    NOT NULL,
    content_type        text    NOT NULL CHECK (content_type IN ('visual_aid', 'leaflet', 'video', 'study_summary',
                                                                  'email_template', 'whatsapp_template')),
    target_specialties  text[],
    key_message         text,
    approved_claims     text,
    language            text    NOT NULL,
    review_reference    text    NOT NULL,
    approved_on         date    NOT NULL,
    expires_on          date    NOT NULL,
    file_blob_path      text    NOT NULL,
    status              text    NOT NULL CHECK (status IN ('active', 'expired', 'withdrawn')),
    embedding           vector(1024),          -- BGE-M3; filled later by the embedding job
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    source_system text NOT NULL DEFAULT 'app', load_batch_id text,
    CHECK (expires_on >= approved_on)
);
CREATE INDEX ix_content_brand ON content (brand_code, content_type);

-- =====================================================================  customers
CREATE TABLE doctor (
    doctor_id                   bigint   PRIMARY KEY,
    doctor_code                 text     NOT NULL UNIQUE,
    registration_no             text,
    registration_council        text,
    full_name                   text     NOT NULL,
    gender                      text     CHECK (gender IN ('Male', 'Female')),
    birth_date                  date,
    qualification               text,
    specialty                   text     NOT NULL,
    years_of_practice           smallint CHECK (years_of_practice >= 0),
    mobile                      text,
    email                       text,
    prescriber_persona          text,
    behavioural_persona         text,
    loyalty_persona             text,
    digital_persona             text,
    in_clinic_engagement        boolean  NOT NULL,
    patient_support             boolean  NOT NULL,
    scientific_engagement       boolean  NOT NULL,
    scientific_out_clinic       boolean  NOT NULL,
    academy_member              boolean  NOT NULL,
    digital_connect_member      boolean  NOT NULL,
    patient_program_user        boolean  NOT NULL,
    consent_email               text     NOT NULL CHECK (consent_email IN ('opted_in', 'opted_out', 'unknown')),
    consent_whatsapp            text     NOT NULL CHECK (consent_whatsapp IN ('opted_in', 'opted_out', 'unknown')),
    consent_sms                 text     NOT NULL CHECK (consent_sms IN ('opted_in', 'opted_out', 'unknown')),
    consent_phone               text     NOT NULL CHECK (consent_phone IN ('opted_in', 'opted_out', 'unknown')),
    consent_updated_at          timestamptz,
    linkedin_url                text,
    x_url                       text,
    public_bio                  text,
    recent_public_topics        text[],
    social_compliance_approved  boolean,
    mdm_status                  text     NOT NULL CHECK (mdm_status IN ('active', 'merged')),
    merged_into_doctor_id       bigint   REFERENCES doctor,
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    source_system text NOT NULL DEFAULT 'app', load_batch_id text,
    CHECK ((mdm_status = 'merged') = (merged_into_doctor_id IS NOT NULL)),
    CHECK (consent_email = 'unknown' OR email IS NOT NULL),
    CHECK (consent_whatsapp = 'unknown' OR mobile IS NOT NULL)
);
CREATE INDEX ix_doctor_name_trgm ON doctor USING gin (full_name gin_trgm_ops);
CREATE INDEX ix_doctor_specialty ON doctor (specialty);

CREATE TABLE clinic (
    clinic_id         bigint  PRIMARY KEY,
    doctor_id         bigint  NOT NULL REFERENCES doctor,
    clinic_name       text    NOT NULL,
    clinic_type       text    NOT NULL CHECK (clinic_type IN ('private_clinic', 'hospital', 'nursing_home')),
    is_primary        boolean NOT NULL,
    address           text    NOT NULL,
    city              text    NOT NULL,
    state             text    NOT NULL,
    pincode           text    NOT NULL CHECK (pincode ~ '^[0-9]{6}$'),
    patch_id          bigint  NOT NULL REFERENCES geography,
    latitude          double precision NOT NULL,
    longitude         double precision NOT NULL,
    opd_schedule      jsonb   NOT NULL,    -- [{"weekday":1,"start_time":"10:00:00","end_time":"13:30:00"}, ...]
    rep_visit_window  jsonb   NOT NULL,
    timing_source     text    NOT NULL CHECK (timing_source IN ('rep_reported', 'doctor_confirmed', 'inferred_from_calls')),
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    source_system text NOT NULL DEFAULT 'app', load_batch_id text
);
CREATE UNIQUE INDEX ux_clinic_primary ON clinic (doctor_id) WHERE is_primary;
CREATE INDEX ix_clinic_patch ON clinic (patch_id);

CREATE TABLE chemist (
    chemist_id       bigint  PRIMARY KEY,
    chemist_name     text    NOT NULL,
    chemist_type     text    NOT NULL CHECK (chemist_type IN ('retail', 'chain', 'hospital_pharmacy')),
    chain_name       text,
    drug_license_no  text    NOT NULL,
    address          text    NOT NULL,
    city             text    NOT NULL,
    state            text    NOT NULL,
    pincode          text    NOT NULL CHECK (pincode ~ '^[0-9]{6}$'),
    patch_id         bigint  NOT NULL REFERENCES geography,
    latitude         double precision NOT NULL,
    longitude        double precision NOT NULL,
    is_active        boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    source_system text NOT NULL DEFAULT 'app', load_batch_id text,
    CHECK ((chemist_type = 'chain') = (chain_name IS NOT NULL))
);

CREATE TABLE mcl (
    mcl_id              bigint   PRIMARY KEY,
    territory_id        bigint   NOT NULL,
    doctor_id           bigint   NOT NULL REFERENCES doctor,
    clinic_id           bigint   NOT NULL REFERENCES clinic,
    patch_id            bigint   NOT NULL REFERENCES geography,
    doctor_class        text     NOT NULL CHECK (doctor_class IN ('A', 'B', 'C')),
    visit_frequency     text     NOT NULL CHECK (visit_frequency IN ('V1', 'V2', 'V3')),
    mcl_position        smallint,
    linked_chemist_ids  bigint[],
    valid_from          date     NOT NULL,
    valid_to            date,
    is_current          boolean  NOT NULL,
    change_reason       text     NOT NULL CHECK (change_reason IN ('initial_list', 'added', 'reclassified')),
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    source_system text NOT NULL DEFAULT 'app', load_batch_id text,
    CHECK (valid_to IS NULL OR valid_to >= valid_from),
    CHECK (is_current = (valid_to IS NULL)),
    CONSTRAINT ex_mcl_no_overlap EXCLUDE USING gist (
        territory_id WITH =, doctor_id WITH =,
        daterange(valid_from, COALESCE(valid_to, 'infinity'::date), '[]') WITH &&)
);
CREATE INDEX ix_mcl_territory_current ON mcl (territory_id) WHERE is_current;
CREATE INDEX ix_mcl_doctor ON mcl (doctor_id);

-- =====================================================================  planning
CREATE TABLE tour_plan (
    tour_plan_id               bigint      PRIMARY KEY,
    employee_id                bigint      NOT NULL,
    territory_id               bigint      NOT NULL,
    plan_date                  date        NOT NULL REFERENCES calendar_day,
    year_month                 integer     NOT NULL,
    activity_type              text        NOT NULL CHECK (activity_type IN ('field_work', 'leave', 'meeting',
                                                                             'training', 'holiday', 'admin')),
    patch_id                   bigint      REFERENCES geography,
    doctor_id                  bigint      REFERENCES doctor,
    clinic_id                  bigint      REFERENCES clinic,
    planned_start_time         time,
    source                     text        NOT NULL CHECK (source IN ('stp_generated', 'rep_created',
                                                                      'agent_suggested', 'booked_slot')),
    status                     text        NOT NULL CHECK (status IN ('draft', 'submitted', 'approved',
                                                                      'rejected', 'revised', 'cancelled')),
    version                    smallint    NOT NULL DEFAULT 1 CHECK (version >= 1),
    submitted_at               timestamptz,
    approved_by                bigint,
    approved_at                timestamptz,
    joint_working_employee_id  bigint,
    is_deviation               boolean     NOT NULL DEFAULT false,
    deviation_reason           text,
    booking_status             text        CHECK (booking_status IN ('proposed', 'requested', 'confirmed', 'declined')),
    booking_confirmed_at       timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    source_system text NOT NULL DEFAULT 'app', load_batch_id text,
    CHECK (year_month = EXTRACT(YEAR FROM plan_date) * 100 + EXTRACT(MONTH FROM plan_date)),
    CHECK ((activity_type = 'field_work') = (doctor_id IS NOT NULL)),
    CHECK ((source = 'booked_slot') = (booking_status IS NOT NULL)),
    CHECK (is_deviation = (deviation_reason IS NOT NULL)),
    CHECK (status <> 'draft' OR submitted_at IS NULL),
    CHECK (status <> 'approved' OR approved_by IS NOT NULL)
);
CREATE INDEX ix_tour_plan_employee_date ON tour_plan (employee_id, plan_date);
CREATE INDEX ix_tour_plan_doctor_date ON tour_plan (doctor_id, plan_date);

CREATE TABLE kpi_target (
    kpi_code          text    NOT NULL CHECK (kpi_code IN ('MCR_COVERAGE', 'MVC')),
    year_month        integer NOT NULL,
    business_unit_id  bigint  REFERENCES business_unit,     -- NULL = company-wide
    target_value      double precision NOT NULL CHECK (target_value BETWEEN 0 AND 100),
    unit              text    NOT NULL,
    comparison        text    NOT NULL CHECK (comparison IN ('gte', 'lte')),
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    source_system text NOT NULL DEFAULT 'app', load_batch_id text,
    CONSTRAINT ux_kpi_target UNIQUE NULLS NOT DISTINCT (kpi_code, year_month, business_unit_id)
);

-- =====================================================================  field activity
CREATE TABLE dcr_call (
    call_id                    bigint      PRIMARY KEY,
    employee_id                bigint      NOT NULL,
    territory_id               bigint      NOT NULL,
    doctor_id                  bigint      NOT NULL REFERENCES doctor,
    clinic_id                  bigint      NOT NULL REFERENCES clinic,
    patch_id                   bigint      NOT NULL REFERENCES geography,
    call_date                  date        NOT NULL REFERENCES calendar_day,
    call_start_time            time        NOT NULL,
    duration_minutes           smallint    CHECK (duration_minutes > 0),
    call_type                  text        NOT NULL CHECK (call_type IN ('in_clinic', 'virtual', 'phone')),
    joint_working_employee_id  bigint,
    tour_plan_id               bigint      UNIQUE REFERENCES tour_plan,
    is_planned                 boolean     NOT NULL,
    call_status                text        NOT NULL CHECK (call_status IN ('completed', 'doctor_unavailable')),
    submitted_at               timestamptz NOT NULL,
    checkin_latitude           double precision,
    checkin_longitude          double precision,
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    source_system text NOT NULL DEFAULT 'app', load_batch_id text,
    CHECK ((call_status = 'completed') = (duration_minutes IS NOT NULL)),
    CHECK (is_planned = (tour_plan_id IS NOT NULL)),
    CHECK ((call_type = 'in_clinic') = (checkin_latitude IS NOT NULL))
);
CREATE INDEX ix_dcr_call_territory_date ON dcr_call (territory_id, call_date);
CREATE INDEX ix_dcr_call_employee_date ON dcr_call (employee_id, call_date);
CREATE INDEX ix_dcr_call_doctor_date ON dcr_call (doctor_id, call_date);
CREATE INDEX ix_dcr_call_date ON dcr_call (call_date);

CREATE TABLE dcr_call_product (
    call_product_id    bigint   PRIMARY KEY,
    call_id            bigint   NOT NULL REFERENCES dcr_call,
    line_type          text     NOT NULL CHECK (line_type IN ('detailing', 'sample', 'input')),
    brand_code         text     NOT NULL,
    sku_code           text     REFERENCES product,
    sequence_no        smallint,
    detailing_seconds  integer  CHECK (detailing_seconds >= 0),
    content_id         bigint   REFERENCES content,
    quantity           integer  CHECK (quantity > 0),
    input_description  text,
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    source_system text NOT NULL DEFAULT 'app', load_batch_id text,
    CHECK (line_type <> 'detailing' OR (detailing_seconds IS NOT NULL AND sequence_no IS NOT NULL AND quantity IS NULL)),
    CHECK (line_type <> 'sample' OR (sku_code IS NOT NULL AND quantity IS NOT NULL)),
    CHECK (line_type <> 'input' OR (input_description IS NOT NULL AND quantity IS NOT NULL))
);
CREATE INDEX ix_dcr_call_product_call ON dcr_call_product (call_id);

CREATE TABLE call_note (
    note_id               bigint      PRIMARY KEY,
    call_id               bigint      NOT NULL REFERENCES dcr_call,
    employee_id           bigint      NOT NULL,
    doctor_id             bigint      NOT NULL REFERENCES doctor,
    recorded_at           timestamptz NOT NULL,
    source                text        NOT NULL CHECK (source IN ('voice', 'text')),
    audio_blob_path       text,
    audio_duration_sec    integer     CHECK (audio_duration_sec > 0),
    audio_format          text,
    transcription_status  text        CHECK (transcription_status IN ('pending', 'done', 'failed')),
    language_detected     text,
    transcript_raw        text,
    transcript_en         text,
    summary               text,
    brands_discussed      text[],
    topics                text[],
    objections            text,
    doctor_commitments    text,
    rep_commitments       text,
    next_step             text,
    next_call_date        date,
    doctor_receptivity    text        CHECK (doctor_receptivity IN ('low', 'medium', 'high')),
    compliance_flags      text[],
    status                text        NOT NULL CHECK (status IN ('draft', 'confirmed')),
    confirmed_at          timestamptz,
    embedding             vector(1024),
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    source_system text NOT NULL DEFAULT 'app', load_batch_id text,
    CHECK ((source = 'voice') = (audio_blob_path IS NOT NULL)),
    CHECK ((status = 'confirmed') = (confirmed_at IS NOT NULL))
);
CREATE INDEX ix_call_note_doctor_time ON call_note (doctor_id, recorded_at);
CREATE INDEX ix_call_note_call ON call_note (call_id);

-- =====================================================================  market
CREATE TABLE rcpa_entry (
    rcpa_id          bigint  PRIMARY KEY,
    audit_date       date    NOT NULL REFERENCES calendar_day,
    year_month       integer NOT NULL,
    employee_id      bigint  NOT NULL,
    territory_id     bigint  NOT NULL,
    chemist_id       bigint  NOT NULL REFERENCES chemist,
    doctor_id        bigint  NOT NULL REFERENCES doctor,
    brand_code       text    NOT NULL,
    prescriptions    integer NOT NULL CHECK (prescriptions > 0),
    quantity_strips  double precision NOT NULL CHECK (quantity_strips > 0),
    value_inr        double precision NOT NULL CHECK (value_inr >= 0),
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    source_system text NOT NULL DEFAULT 'app', load_batch_id text,
    CHECK (year_month = EXTRACT(YEAR FROM audit_date) * 100 + EXTRACT(MONTH FROM audit_date))
);
CREATE INDEX ix_rcpa_territory_month ON rcpa_entry (territory_id, year_month);
CREATE INDEX ix_rcpa_doctor_brand_date ON rcpa_entry (doctor_id, brand_code, audit_date);

CREATE TABLE doctor_brand_plan (
    territory_id         bigint   NOT NULL,
    doctor_id            bigint   NOT NULL REFERENCES doctor,
    brand_code           text     NOT NULL,
    year_month           integer  NOT NULL,
    potential_value_inr  double precision NOT NULL CHECK (potential_value_inr >= 0),
    potential_rx         double precision NOT NULL CHECK (potential_rx >= 0),
    potential_strips     double precision NOT NULL CHECK (potential_strips >= 0),
    target_value_inr     double precision,
    target_rx            double precision,
    target_strips        double precision,
    brand_priority       text     NOT NULL CHECK (brand_priority ~ '^P[0-9]+$'),
    brand_rank           smallint NOT NULL CHECK (brand_rank >= 1),
    is_focus_brand       boolean  NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    source_system text NOT NULL DEFAULT 'app', load_batch_id text,
    PRIMARY KEY (territory_id, doctor_id, brand_code, year_month),
    CHECK (brand_priority = 'P' || brand_rank),
    CHECK (is_focus_brand = (target_rx IS NOT NULL))
);

CREATE TABLE formulary_listing (
    listing_id      bigint  PRIMARY KEY,
    clinic_id       bigint  NOT NULL REFERENCES clinic,
    brand_code      text    NOT NULL,
    listing_status  text    NOT NULL CHECK (listing_status IN ('listed', 'not_listed', 'under_review')),
    effective_from  date    NOT NULL,
    effective_to    date,
    notes           text,
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    source_system text NOT NULL DEFAULT 'app', load_batch_id text,
    CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CONSTRAINT ex_formulary_no_overlap EXCLUDE USING gist (
        clinic_id WITH =, brand_code WITH =,
        daterange(effective_from, COALESCE(effective_to, 'infinity'::date), '[]') WITH &&)
);

-- =====================================================================  engagement and AI
CREATE TABLE communication (
    communication_id  bigint      PRIMARY KEY,
    doctor_id         bigint      NOT NULL REFERENCES doctor,
    employee_id       bigint,
    territory_id      bigint      NOT NULL,
    channel           text        NOT NULL CHECK (channel IN ('email', 'whatsapp', 'sms', 'webinar', 'portal')),
    direction         text        NOT NULL CHECK (direction IN ('outbound', 'inbound')),
    campaign_id       text,
    content_id        bigint      REFERENCES content,
    subject           text,
    body              text,
    generated_by      text        NOT NULL CHECK (generated_by IN ('agent', 'rep', 'central', 'doctor')),
    consent_checked   boolean     NOT NULL,
    status            text        NOT NULL CHECK (status IN ('draft', 'approved', 'rejected', 'sent', 'delivered', 'failed')),
    approved_by       bigint,
    approved_at       timestamptz,
    sent_at           timestamptz,
    delivered_at      timestamptz,
    opened_at         timestamptz,
    clicked_at        timestamptz,
    responded_at      timestamptz,
    response_type     text        CHECK (response_type IN ('reply', 'call_back', 'registered', 'unsubscribed')),
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    source_system text NOT NULL DEFAULT 'app', load_batch_id text,
    CHECK (direction = 'inbound' OR consent_checked),
    CHECK (status NOT IN ('delivered', 'failed') OR sent_at IS NOT NULL),
    CHECK (delivered_at IS NULL OR delivered_at >= sent_at),
    CHECK (opened_at IS NULL OR opened_at >= delivered_at),
    CHECK (responded_at IS NULL OR responded_at >= opened_at)
);
CREATE INDEX ix_communication_doctor_sent ON communication (doctor_id, sent_at);
CREATE INDEX ix_communication_employee_sent ON communication (employee_id, sent_at);

CREATE TABLE nba_recommendation (
    recommendation_id  bigint      PRIMARY KEY,
    generated_at       timestamptz NOT NULL,
    employee_id        bigint      NOT NULL,
    territory_id       bigint      NOT NULL,
    doctor_id          bigint      NOT NULL REFERENCES doctor,
    action_type        text        NOT NULL CHECK (action_type IN ('visit', 'detail_brand', 'send_content',
                                                                    'give_sample', 'follow_up')),
    brand_code         text,
    content_id         bigint      REFERENCES content,
    reason_codes       text[]      NOT NULL,
    score              double precision NOT NULL CHECK (score BETWEEN 0 AND 1),
    engine_version     text        NOT NULL,
    status             text        NOT NULL CHECK (status IN ('shown', 'accepted', 'dismissed', 'completed')),
    status_at          timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    source_system text NOT NULL DEFAULT 'app', load_batch_id text,
    CHECK (action_type NOT IN ('detail_brand', 'give_sample') OR brand_code IS NOT NULL)
);
CREATE INDEX ix_nba_employee_generated ON nba_recommendation (employee_id, generated_at);

CREATE TABLE agent_action_log (
    action_id          bigint      PRIMARY KEY,
    occurred_at        timestamptz NOT NULL,
    employee_id        bigint      NOT NULL,
    agent_name         text        NOT NULL,
    action_type        text        NOT NULL,
    target_table       text        NOT NULL CHECK (target_table IN ('call_note', 'tour_plan', 'communication',
                                                                     'nba_recommendation')),
    target_id          bigint      NOT NULL,
    input_summary      text,
    approval_required  boolean     NOT NULL,
    approved_by        bigint,
    approved_at        timestamptz,
    outcome            text        NOT NULL CHECK (outcome IN ('success', 'rejected', 'failed')),
    error_message      text,
    trace_id           text        NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    source_system text NOT NULL DEFAULT 'app', load_batch_id text,
    CHECK (NOT approval_required OR outcome <> 'success' OR approved_by IS NOT NULL)
);
CREATE INDEX ix_agent_action_log_employee_time ON agent_action_log (employee_id, occurred_at);

-- audit trail is insert-only: updates and deletes are refused (rebuilds use TRUNCATE)
CREATE FUNCTION forbid_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% is insert-only', TG_TABLE_NAME;
END $$;
CREATE TRIGGER trg_agent_action_log_insert_only
    BEFORE UPDATE OR DELETE ON agent_action_log FOR EACH ROW EXECUTE FUNCTION forbid_change();
