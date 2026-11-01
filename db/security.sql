-- Row-level security: the database enforces who sees what.
-- The app connects as role mr_app and sets the user per transaction:
--     SELECT set_config('app.employee_id', '990001', true);
-- BO -> own territory; ABM / RBM / ZBM -> every territory in their reporting tree.
-- No identity set -> protected tables return no rows (fail closed).
-- Recreated by scripts/build_db.py after every load.

-- login role for the API and agents (password set by build_db.py from .env)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mr_app') THEN
        CREATE ROLE mr_app LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
    END IF;
END $$;

-- ------------------------------------------------------------------ identity helpers
CREATE OR REPLACE FUNCTION core.current_employee_id() RETURNS bigint
LANGUAGE sql STABLE AS $$
    SELECT NULLIF(current_setting('app.employee_id', true), '')::bigint
$$;

-- self + everyone reporting to the current user, directly or indirectly (current assignments)
CREATE OR REPLACE FUNCTION core.visible_employee_ids() RETURNS bigint[]
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = core, pg_temp AS $$
    WITH RECURSIVE team AS (
        SELECT employee_id FROM employee
        WHERE employee_id = current_employee_id() AND is_current
        UNION
        SELECT e.employee_id FROM employee e JOIN team t ON e.manager_employee_id = t.employee_id
        WHERE e.is_current
    )
    SELECT COALESCE(array_agg(employee_id), '{}') FROM team
$$;

CREATE OR REPLACE FUNCTION core.visible_territory_ids() RETURNS bigint[]
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = core, pg_temp AS $$
    SELECT COALESCE(array_agg(DISTINCT territory_id), '{}') FROM employee
    WHERE is_current AND territory_id IS NOT NULL AND employee_id = ANY (visible_employee_ids())
$$;

CREATE OR REPLACE FUNCTION core.visible_patch_ids() RETURNS bigint[]
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = core, pg_temp AS $$
    SELECT COALESCE(array_agg(patch_id), '{}') FROM geography WHERE territory_id = ANY (visible_territory_ids())
$$;

CREATE OR REPLACE FUNCTION core.visible_doctor_ids() RETURNS bigint[]
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = core, pg_temp AS $$
    SELECT COALESCE(array_agg(DISTINCT doctor_id), '{}') FROM clinic WHERE patch_id = ANY (visible_patch_ids())
$$;

-- ------------------------------------------------------------------ policies
-- (SELECT f())::bigint[] makes Postgres evaluate the function once per query, not once per row.
DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['geography', 'mcl', 'dcr_call', 'tour_plan', 'rcpa_entry',
                             'doctor_brand_plan', 'communication', 'nba_recommendation'] LOOP
        EXECUTE format('ALTER TABLE core.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('CREATE POLICY territory_scope ON core.%I FOR SELECT USING '
                       '(territory_id = ANY ((SELECT core.visible_territory_ids())::bigint[]))', t);
    END LOOP;
END $$;

ALTER TABLE core.employee ENABLE ROW LEVEL SECURITY;
CREATE POLICY team_scope ON core.employee FOR SELECT
    USING (employee_id = ANY ((SELECT core.visible_employee_ids())::bigint[]));

ALTER TABLE core.agent_action_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY team_scope ON core.agent_action_log FOR SELECT
    USING (employee_id = ANY ((SELECT core.visible_employee_ids())::bigint[]));

ALTER TABLE core.doctor ENABLE ROW LEVEL SECURITY;
CREATE POLICY doctor_scope ON core.doctor FOR SELECT
    USING (doctor_id = ANY ((SELECT core.visible_doctor_ids())::bigint[]));

ALTER TABLE core.clinic ENABLE ROW LEVEL SECURITY;
CREATE POLICY patch_scope ON core.clinic FOR SELECT
    USING (patch_id = ANY ((SELECT core.visible_patch_ids())::bigint[]));

ALTER TABLE core.chemist ENABLE ROW LEVEL SECURITY;
CREATE POLICY patch_scope ON core.chemist FOR SELECT
    USING (patch_id = ANY ((SELECT core.visible_patch_ids())::bigint[]));

-- child tables follow their parent (the subquery is itself filtered by the parent's policy)
ALTER TABLE core.dcr_call_product ENABLE ROW LEVEL SECURITY;
CREATE POLICY parent_scope ON core.dcr_call_product FOR SELECT
    USING (call_id IN (SELECT call_id FROM core.dcr_call));

ALTER TABLE core.call_note ENABLE ROW LEVEL SECURITY;
CREATE POLICY parent_scope ON core.call_note FOR SELECT
    USING (call_id IN (SELECT call_id FROM core.dcr_call));

ALTER TABLE core.formulary_listing ENABLE ROW LEVEL SECURITY;
CREATE POLICY parent_scope ON core.formulary_listing FOR SELECT
    USING (clinic_id IN (SELECT clinic_id FROM core.clinic));

-- reference tables (calendar_day, business_unit, product, content, kpi_target) stay readable by all

-- ------------------------------------------------------------------ grants (read-only for now)
GRANT USAGE ON SCHEMA core, analytics TO mr_app;
GRANT SELECT ON ALL TABLES IN SCHEMA core, analytics TO mr_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA core, analytics TO mr_app;
