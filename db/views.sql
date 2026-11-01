-- Gold layer: analytical views over schema core (schema `analytics`).
-- Recreated by scripts/build_db.py after every load.
-- Every view uses security_invoker = true: it runs with the caller's rights,
-- so row-level security on the underlying tables still applies.
CREATE SCHEMA IF NOT EXISTS analytics;

-- ------------------------------------------------------------------ helpers
-- Snapshot date: the last day with field activity (data ends here).
CREATE OR REPLACE FUNCTION analytics.as_of_date() RETURNS date
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = core, pg_temp AS $$
    SELECT MAX(call_date) FROM dcr_call
$$;

-- Add n months to a YYYYMM integer (n may be negative).
CREATE OR REPLACE FUNCTION analytics.ym_add(ym integer, n integer) RETURNS integer
LANGUAGE sql IMMUTABLE AS $$
    SELECT (EXTRACT(YEAR FROM d) * 100 + EXTRACT(MONTH FROM d))::int
    FROM (SELECT make_date(ym / 100, ym % 100, 1) + make_interval(months => n) AS d) x
$$;

CREATE OR REPLACE FUNCTION analytics.ym_of(d date) RETURNS integer
LANGUAGE sql IMMUTABLE AS $$ SELECT (EXTRACT(YEAR FROM d) * 100 + EXTRACT(MONTH FROM d))::int $$;

-- The BO who held a territory on a date (also visible for months before a handover).
CREATE OR REPLACE FUNCTION analytics.territory_bo(p_territory_id bigint, p_on date)
RETURNS TABLE (employee_id bigint, employee_name text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = core, pg_temp AS $$
    SELECT employee_id, employee_name FROM employee
    WHERE designation = 'BO' AND territory_id = p_territory_id
      AND p_on BETWEEN valid_from AND COALESCE(valid_to, 'infinity'::date)
    LIMIT 1
$$;

-- Display name of any employee (e.g. the manager who joined a call or approved a plan).
CREATE OR REPLACE FUNCTION analytics.employee_name(p_employee_id bigint) RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = core, pg_temp AS $$
    SELECT employee_name FROM employee WHERE employee_id = p_employee_id ORDER BY valid_from DESC LIMIT 1
$$;

-- Current manager of an employee.
CREATE OR REPLACE FUNCTION analytics.employee_manager(p_employee_id bigint)
RETURNS TABLE (employee_id bigint, employee_name text, designation text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = core, pg_temp AS $$
    SELECT m.employee_id, m.employee_name, m.designation
    FROM employee e JOIN employee m ON m.employee_id = e.manager_employee_id AND m.is_current
    WHERE e.employee_id = p_employee_id AND e.is_current
$$;

-- ------------------------------------------------------------------ brand
-- One row per brand (own and competitor); product holds one row per SKU.
CREATE OR REPLACE VIEW analytics.brand WITH (security_invoker = true) AS
SELECT DISTINCT ON (brand_code)
       brand_code, brand_name, is_own_brand, manufacturer, business_unit_id, therapy_area,
       molecule_class, is_growth_brand, is_device, price_per_strip_inr
FROM core.product
ORDER BY brand_code, sku_code;

-- ------------------------------------------------------------------ doctor_visit_compliance
-- One row per month x territory x doctor on the MCL (Master Customer List).
-- A doctor counts for a month if listed on the first day of that month.
-- The latest month is month-to-date (data ends on the as-of date).
CREATE OR REPLACE VIEW analytics.doctor_visit_compliance WITH (security_invoker = true) AS
WITH months AS (
    SELECT DISTINCT make_date(year, month, 1) AS month_start,
           (make_date(year, month, 1) + INTERVAL '1 month' - INTERVAL '1 day')::date AS month_end,
           year_month
    FROM core.calendar_day
    WHERE calendar_date BETWEEN (SELECT MIN(call_date) FROM core.dcr_call)
                            AND (SELECT MAX(call_date) FROM core.dcr_call)
),
listed AS (
    SELECT m.year_month, m.month_end, l.territory_id, l.doctor_id, l.doctor_class, l.visit_frequency,
           substr(l.visit_frequency, 2)::int AS required_visits
    FROM months m
    JOIN core.mcl l
      ON l.valid_from <= m.month_start
     AND COALESCE(l.valid_to, 'infinity'::date) >= m.month_start
),
visits AS (
    SELECT territory_id, doctor_id, analytics.ym_of(call_date) AS year_month, COUNT(*) AS visits_done
    FROM core.dcr_call
    WHERE call_status = 'completed'
    GROUP BY 1, 2, 3
)
SELECT l.year_month,
       l.territory_id,
       l.doctor_id,
       l.doctor_class,
       l.visit_frequency,
       l.required_visits,
       COALESCE(v.visits_done, 0)                                   AS visits_done,
       GREATEST(l.required_visits - COALESCE(v.visits_done, 0), 0)  AS visits_pending,
       COALESCE(v.visits_done, 0) > 0                               AS is_covered,
       COALESCE(v.visits_done, 0) >= l.required_visits              AS is_compliant,
       last_visit.call_date                                         AS last_visit_date
FROM listed l
LEFT JOIN visits v USING (territory_id, doctor_id, year_month)
LEFT JOIN LATERAL (
    SELECT c.call_date FROM core.dcr_call c
    WHERE c.doctor_id = l.doctor_id AND c.territory_id = l.territory_id
      AND c.call_status = 'completed' AND c.call_date <= l.month_end
    ORDER BY c.call_date DESC LIMIT 1
) last_visit ON true;

-- ------------------------------------------------------------------ rep_monthly_kpi
-- One row per month x territory: MCR coverage, multi-visit compliance and calls per
-- field day against their targets. The latest month is month-to-date.
CREATE OR REPLACE VIEW analytics.rep_monthly_kpi WITH (security_invoker = true) AS
WITH comp AS (
    SELECT year_month, territory_id, COUNT(*) AS listed_doctors,
           SUM(is_covered::int) AS covered_doctors, SUM(is_compliant::int) AS compliant_doctors,
           SUM(visits_pending) AS visits_pending
    FROM analytics.doctor_visit_compliance
    GROUP BY 1, 2
),
calls AS (
    SELECT territory_id, analytics.ym_of(call_date) AS year_month,
           COUNT(*) FILTER (WHERE call_status = 'completed')                         AS calls_completed,
           COUNT(DISTINCT call_date) FILTER (WHERE call_status = 'completed')        AS field_days,
           ROUND(AVG(duration_minutes) FILTER (WHERE call_status = 'completed'), 1)  AS avg_call_minutes,
           COUNT(DISTINCT call_date) FILTER (WHERE joint_working_employee_id IS NOT NULL) AS joint_working_days,
           COUNT(*) FILTER (WHERE call_status = 'completed' AND NOT is_planned)      AS unplanned_calls
    FROM core.dcr_call
    GROUP BY 1, 2
),
terr AS (SELECT DISTINCT territory_id, business_unit_id FROM core.geography)
SELECT c.year_month,
       c.territory_id,
       t.business_unit_id,
       bo.employee_id,
       bo.employee_name,
       c.listed_doctors,
       c.covered_doctors,
       c.compliant_doctors,
       c.visits_pending,
       ROUND(100.0 * c.covered_doctors / NULLIF(c.listed_doctors, 0), 1)    AS mcr_pct,
       ROUND(100.0 * c.compliant_doctors / NULLIF(c.listed_doctors, 0), 1)  AS mvc_pct,
       mcr.target_value                                                      AS mcr_target_pct,
       mvc.target_value                                                      AS mvc_target_pct,
       100.0 * c.covered_doctors / NULLIF(c.listed_doctors, 0) >= mcr.target_value   AS mcr_met,
       100.0 * c.compliant_doctors / NULLIF(c.listed_doctors, 0) >= mvc.target_value AS mvc_met,
       k.calls_completed,
       k.field_days,
       ROUND(k.calls_completed::numeric / NULLIF(k.field_days, 0), 1)       AS calls_per_day,
       b.calls_per_day_lower                                                 AS calls_per_day_target,
       CASE WHEN k.calls_completed::numeric / NULLIF(k.field_days, 0) < b.calls_per_day_lower THEN 'below'
            WHEN k.calls_completed::numeric / NULLIF(k.field_days, 0) >= b.calls_per_day_upper THEN 'above'
            ELSE 'within' END                                                AS call_band,
       k.avg_call_minutes,
       k.joint_working_days,
       k.unplanned_calls,
       c.year_month = (SELECT analytics.ym_of(analytics.as_of_date()))       AS is_month_to_date
FROM comp c
JOIN terr t USING (territory_id)
JOIN core.business_unit b ON b.business_unit_id = t.business_unit_id
LEFT JOIN calls k USING (territory_id, year_month)
LEFT JOIN core.kpi_target mcr ON mcr.kpi_code = 'MCR_COVERAGE' AND mcr.year_month = c.year_month
                             AND mcr.business_unit_id IS NULL
LEFT JOIN core.kpi_target mvc ON mvc.kpi_code = 'MVC' AND mvc.year_month = c.year_month
                             AND mvc.business_unit_id IS NULL
LEFT JOIN LATERAL analytics.territory_bo(c.territory_id, make_date(c.year_month / 100, c.year_month % 100, 1)) bo
       ON true;

-- ------------------------------------------------------------------ rx_monthly
-- Audited prescriptions per month x territory x doctor x brand (own and competitor).
-- Months without an audit have no row.
CREATE OR REPLACE VIEW analytics.rx_monthly WITH (security_invoker = true) AS
SELECT r.year_month,
       r.territory_id,
       r.doctor_id,
       r.brand_code,
       b.brand_name,
       b.is_own_brand,
       b.molecule_class,
       b.therapy_area,
       SUM(r.prescriptions)            AS prescriptions,
       ROUND(SUM(r.quantity_strips)::numeric, 1) AS quantity_strips,
       ROUND(SUM(r.value_inr)::numeric, 2)       AS value_inr,
       COUNT(DISTINCT r.audit_date)    AS audits,
       MAX(r.audit_date)               AS last_audit_date
FROM core.rcpa_entry r
JOIN analytics.brand b USING (brand_code)
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8;

-- ------------------------------------------------------------------ market_share
-- Own-brand share of audited prescriptions per month x territory x therapy class.
CREATE OR REPLACE VIEW analytics.market_share WITH (security_invoker = true) AS
SELECT year_month,
       territory_id,
       molecule_class,
       therapy_area,
       SUM(prescriptions) FILTER (WHERE is_own_brand)      AS own_rx,
       SUM(prescriptions) FILTER (WHERE NOT is_own_brand)  AS competitor_rx,
       SUM(prescriptions)                                  AS total_rx,
       ROUND(100.0 * COALESCE(SUM(prescriptions) FILTER (WHERE is_own_brand), 0)
             / NULLIF(SUM(prescriptions), 0), 1)           AS own_share_pct,
       SUM(value_inr) FILTER (WHERE is_own_brand)          AS own_value_inr,
       SUM(value_inr)                                      AS total_value_inr
FROM analytics.rx_monthly
GROUP BY 1, 2, 3, 4;

-- ------------------------------------------------------------------ doctor_360
-- One row per doctor on a current MCL: profile, this month's visits, 3-month Rx and
-- share with trend, latest confirmed note, consent and digital response.
CREATE OR REPLACE VIEW analytics.doctor_360 WITH (security_invoker = true) AS
WITH snap AS (
    SELECT analytics.as_of_date() AS as_of, analytics.ym_of(analytics.as_of_date()) AS ym
),
own AS (SELECT DISTINCT brand_code, is_own_brand FROM core.product),
rx AS (   -- last 6 months of audits, aggregated once for all visible doctors
    SELECT r.doctor_id, r.territory_id,
           SUM(r.prescriptions) FILTER (WHERE o.is_own_brand AND r.year_month > analytics.ym_add(s.ym, -3))  AS own_rx_3m,
           SUM(r.prescriptions) FILTER (WHERE r.year_month > analytics.ym_add(s.ym, -3))                   AS total_rx_3m,
           SUM(r.prescriptions) FILTER (WHERE o.is_own_brand AND r.year_month <= analytics.ym_add(s.ym, -3)) AS own_rx_prev_3m
    FROM core.rcpa_entry r CROSS JOIN snap s JOIN own o USING (brand_code)
    WHERE r.year_month > analytics.ym_add(s.ym, -6)
    GROUP BY 1, 2
),
wa AS (   -- WhatsApp touches in the last 90 days
    SELECT x.doctor_id,
           COUNT(*) FILTER (WHERE x.direction = 'outbound' AND x.sent_at IS NOT NULL) AS messages_90d,
           COUNT(*) FILTER (WHERE x.responded_at IS NOT NULL)                         AS responses_90d
    FROM core.communication x CROSS JOIN snap s
    WHERE x.channel = 'whatsapp' AND x.sent_at >= s.as_of - INTERVAL '90 days'
    GROUP BY 1
)
SELECT d.doctor_id,
       d.doctor_code,
       d.full_name,
       d.specialty,
       d.qualification,
       d.years_of_practice,
       m.territory_id,
       m.doctor_class,
       m.visit_frequency,
       m.patch_id,
       c.clinic_name          AS primary_clinic,
       c.clinic_type          AS primary_clinic_type,
       c.city,
       v.visits_done          AS visits_done_this_month,
       v.required_visits      AS visits_required_this_month,
       v.visits_pending       AS visits_pending_this_month,
       v.last_visit_date,
       s.as_of - v.last_visit_date AS days_since_last_visit,
       rx.own_rx_3m,
       rx.total_rx_3m,
       ROUND(100.0 * rx.own_rx_3m / NULLIF(rx.total_rx_3m, 0), 1)     AS own_share_3m_pct,
       rx.own_rx_prev_3m,
       ROUND(100.0 * (rx.own_rx_3m - rx.own_rx_prev_3m) / NULLIF(rx.own_rx_prev_3m, 0), 1) AS own_rx_trend_pct,
       note.recorded_at::date AS last_note_date,
       note.summary           AS last_note_summary,
       note.objections        AS last_note_objections,
       note.doctor_receptivity AS last_receptivity,
       d.prescriber_persona,
       d.behavioural_persona,
       d.loyalty_persona,
       d.digital_persona,
       d.consent_email,
       d.consent_whatsapp,
       COALESCE(wa.messages_90d, 0)  AS whatsapp_messages_90d,
       COALESCE(wa.responses_90d, 0) AS whatsapp_responses_90d
FROM core.mcl m
CROSS JOIN snap s
JOIN core.doctor d USING (doctor_id)
LEFT JOIN core.clinic c ON c.clinic_id = m.clinic_id
LEFT JOIN analytics.doctor_visit_compliance v
       ON v.doctor_id = m.doctor_id AND v.territory_id = m.territory_id AND v.year_month = s.ym
LEFT JOIN rx ON rx.doctor_id = m.doctor_id AND rx.territory_id = m.territory_id
LEFT JOIN wa ON wa.doctor_id = m.doctor_id
LEFT JOIN LATERAL (
    SELECT n.recorded_at, n.summary, n.objections, n.doctor_receptivity FROM core.call_note n
    WHERE n.doctor_id = m.doctor_id AND n.status = 'confirmed'
    ORDER BY n.recorded_at DESC LIMIT 1
) note ON true
WHERE m.is_current;

-- view descriptions live in db/comments.sql
