"""Integrity checks across the generated Parquet files. Fails loudly."""

import duckdb

from generator import config

P = config.PARQUET_DIR


def _rows(con, sql):
    return con.execute(sql).fetchall()


def run() -> None:
    con = duckdb.connect()
    for f in sorted(P.glob("*.parquet")):
        con.execute(f"CREATE VIEW {f.stem} AS SELECT * FROM '{f}'")

    checks = {
        # calendar
        "calendar: one row per day, no gaps":
            f"""SELECT COUNT(*) <> DATE_DIFF('day', DATE '{config.CALENDAR_START}', DATE '{config.CALENDAR_END}') + 1
                   OR COUNT(DISTINCT calendar_date) <> COUNT(*) FROM calendar_day""",
        "calendar: fiscal quarter 1 starts in April":
            "SELECT COUNT(*) FROM calendar_day WHERE month = 4 AND fiscal_quarter <> 1",
        "calendar: holiday name present for every holiday":
            "SELECT COUNT(*) FROM calendar_day WHERE (is_national_holiday OR holiday_states IS NOT NULL) AND holiday_name IS NULL",
        # geography
        "geography: each territory maps to one SBU / HQ / region / zone":
            """SELECT COUNT(*) FROM (SELECT territory_id FROM geography GROUP BY territory_id
               HAVING COUNT(DISTINCT (business_unit_id, hq_id, region_id, zone_id)) > 1)""",
        "geography: coordinates inside India":
            "SELECT COUNT(*) FROM geography WHERE latitude NOT BETWEEN 6 AND 37 OR longitude NOT BETWEEN 68 AND 98",
        # employee
        "employee: assignment periods of one person do not overlap":
            """SELECT COUNT(*) FROM employee a JOIN employee b
               ON a.employee_id = b.employee_id AND a.assignment_id < b.assignment_id
              AND a.valid_from <= COALESCE(b.valid_to, DATE '9999-12-31')
              AND b.valid_from <= COALESCE(a.valid_to, DATE '9999-12-31')""",
        "employee: exactly one BO per territory on the as-of date":
            f"""SELECT COUNT(*) FROM (SELECT g.territory_id, COUNT(e.employee_id) n
               FROM (SELECT DISTINCT territory_id FROM geography) g
               LEFT JOIN employee e ON e.territory_id = g.territory_id AND e.designation = 'BO'
                AND DATE '{config.AS_OF_DATE}' BETWEEN e.valid_from AND COALESCE(e.valid_to, DATE '9999-12-31')
               GROUP BY g.territory_id HAVING n <> 1)""",
        "employee: territory never left without a BO (no gap in handover)":
            """SELECT COUNT(*) FROM employee a JOIN employee b
               ON a.territory_id = b.territory_id AND a.designation = 'BO' AND b.designation = 'BO'
              AND a.valid_to IS NOT NULL AND b.valid_from > a.valid_to
              AND b.valid_from <> a.valid_to + 1
              AND NOT EXISTS (SELECT 1 FROM employee c WHERE c.territory_id = a.territory_id
                              AND c.valid_from = a.valid_to + 1)""",
        "employee: BO territory exists and is in the BO's SBU":
            """SELECT COUNT(*) FROM employee e LEFT JOIN (SELECT DISTINCT territory_id, business_unit_id FROM geography) g
               USING (territory_id) WHERE e.territory_id IS NOT NULL
               AND (g.territory_id IS NULL OR g.business_unit_id <> e.business_unit_id)""",
        "employee: manager exists, is one level up, same SBU, and in post during the period":
            """SELECT COUNT(*) FROM employee e
               WHERE e.manager_employee_id IS NOT NULL AND NOT EXISTS (
                 SELECT 1 FROM employee m WHERE m.employee_id = e.manager_employee_id
                   AND m.business_unit_id = e.business_unit_id
                   AND (e.designation, m.designation) IN (('BO','ABM'), ('ABM','RBM'), ('RBM','ZBM'))
                   AND m.valid_from <= e.valid_from
                   AND COALESCE(m.valid_to, DATE '9999-12-31') >= COALESCE(e.valid_to, DATE '9999-12-31'))""",
        "employee: assignment starts on or after joining date":
            "SELECT COUNT(*) FROM employee WHERE valid_from < joining_date",
        "employee: only ZBMs have no manager":
            "SELECT COUNT(*) FROM employee WHERE manager_employee_id IS NULL AND designation <> 'ZBM'",
        "employee: current login codes unique":
            "SELECT COUNT(*) - COUNT(DISTINCT employee_code) FROM employee WHERE is_current",
        "employee: one employee keeps one code":
            "SELECT COUNT(*) FROM (SELECT employee_id FROM employee GROUP BY 1 HAVING COUNT(DISTINCT employee_code) > 1)",
        "employee / doctor: mobiles are synthetic (+91 then 0 and 9 digits, never a real mobile)":
            """SELECT (SELECT COUNT(*) FROM employee WHERE NOT regexp_full_match(mobile, '\\+910[0-9]{9}'))
                    + (SELECT COUNT(*) FROM doctor WHERE mobile IS NOT NULL AND NOT regexp_full_match(mobile, '\\+910[0-9]{9}'))""",
        # doctor
        "doctor: doctor_code unique":
            "SELECT COUNT(*) - COUNT(DISTINCT doctor_code) FROM doctor",
        "doctor: merged records point to an active doctor":
            """SELECT COUNT(*) FROM doctor d LEFT JOIN doctor s ON d.merged_into_doctor_id = s.doctor_id
               WHERE d.mdm_status = 'merged' AND (s.doctor_id IS NULL OR s.mdm_status <> 'active')""",
        "doctor: email/WhatsApp consent only when the contact exists":
            """SELECT COUNT(*) FROM doctor WHERE (consent_email <> 'unknown' AND email IS NULL)
               OR (consent_whatsapp <> 'unknown' AND mobile IS NULL)""",
        "doctor: emails only on example.com":
            "SELECT COUNT(*) FROM doctor WHERE email IS NOT NULL AND email NOT LIKE '%@example.com'",
        # mcl
        "mcl: periods of one territory x doctor do not overlap":
            """SELECT COUNT(*) FROM mcl a JOIN mcl b ON a.territory_id = b.territory_id
               AND a.doctor_id = b.doctor_id AND a.mcl_id < b.mcl_id
               AND a.valid_from <= COALESCE(b.valid_to, DATE '9999-12-31')
               AND b.valid_from <= COALESCE(a.valid_to, DATE '9999-12-31')""",
        "mcl / employee: validity periods are not inverted (valid_to >= valid_from)":
            """SELECT (SELECT COUNT(*) FROM mcl WHERE valid_to < valid_from)
                    + (SELECT COUNT(*) FROM employee WHERE valid_to < valid_from)""",
        "mcl: about 120 current doctors per territory":
            """SELECT COUNT(*) FROM (SELECT territory_id, COUNT(*) n FROM mcl WHERE is_current
               GROUP BY 1 HAVING n NOT BETWEEN 115 AND 125)""",
        "mcl: doctor is active and patch belongs to the territory":
            """SELECT COUNT(*) FROM mcl m LEFT JOIN doctor d USING (doctor_id) LEFT JOIN geography g USING (patch_id)
               WHERE d.mdm_status IS DISTINCT FROM 'active' OR g.territory_id IS DISTINCT FROM m.territory_id""",
        "mcl: frequency fits class (A V2-V3, B V2, C V1)":
            """SELECT COUNT(*) FROM mcl WHERE NOT ((doctor_class = 'A' AND visit_frequency IN ('V2','V3'))
               OR (doctor_class = 'B' AND visit_frequency = 'V2') OR (doctor_class = 'C' AND visit_frequency = 'V1'))""",
        # dcr_call
        "dcr_call: caller was the territory's BO on the call date":
            """SELECT COUNT(*) FROM dcr_call c WHERE NOT EXISTS (SELECT 1 FROM employee e
               WHERE e.employee_id = c.employee_id AND e.designation = 'BO' AND e.territory_id = c.territory_id
               AND c.call_date BETWEEN e.valid_from AND COALESCE(e.valid_to, DATE '9999-12-31'))""",
        "dcr_call: no calls after the as-of date or on Sundays / holidays":
            f"""SELECT COUNT(*) FROM dcr_call c JOIN calendar_day k ON k.calendar_date = c.call_date
               JOIN (SELECT DISTINCT territory_id, state FROM geography WHERE patch_id % 100 = 1) g USING (territory_id)
               WHERE c.call_date > DATE '{config.AS_OF_DATE}' OR k.is_weekend OR k.is_national_holiday
                  OR list_contains(k.holiday_states, g.state)""",
        "dcr_call: doctor active and patch in territory":
            """SELECT COUNT(*) FROM dcr_call c LEFT JOIN doctor d USING (doctor_id) LEFT JOIN geography g USING (patch_id)
               WHERE d.mdm_status IS DISTINCT FROM 'active' OR g.territory_id IS DISTINCT FROM c.territory_id""",
        "dcr_call: a rep's calls on a day do not overlap":
            """SELECT COUNT(*) FROM (SELECT employee_id, call_date, call_start_time,
               LEAD(call_start_time) OVER (PARTITION BY employee_id, call_date ORDER BY call_start_time) nxt,
               COALESCE(duration_minutes, 5) dur FROM dcr_call)
               WHERE nxt IS NOT NULL AND call_start_time + INTERVAL (dur) MINUTE > nxt""",
        "dcr_call: calls between 09:00 and 22:00":
            "SELECT COUNT(*) FROM dcr_call WHERE call_start_time NOT BETWEEN TIME '09:00' AND TIME '22:00'",
        "dcr_call: completed calls have a duration, unavailable ones do not":
            """SELECT COUNT(*) FROM dcr_call WHERE (call_status = 'completed') <> (duration_minutes IS NOT NULL)""",
        "dcr_call: joint worker is the BO's ABM or that ABM's RBM on the day":
            """SELECT COUNT(*) FROM dcr_call c WHERE joint_working_employee_id IS NOT NULL AND NOT EXISTS (
               SELECT 1 FROM employee bo JOIN employee abm ON abm.employee_id = bo.manager_employee_id
               WHERE bo.employee_id = c.employee_id
                 AND c.call_date BETWEEN bo.valid_from AND COALESCE(bo.valid_to, DATE '9999-12-31')
                 AND c.call_date BETWEEN abm.valid_from AND COALESCE(abm.valid_to, DATE '9999-12-31')
                 AND c.joint_working_employee_id IN (abm.employee_id, abm.manager_employee_id))""",
        "dcr_call: planned flag matches tour_plan_id; plan id used once":
            """SELECT (SELECT COUNT(*) FROM dcr_call WHERE is_planned <> (tour_plan_id IS NOT NULL))
                    + (SELECT COUNT(*) - COUNT(DISTINCT tour_plan_id) FROM dcr_call WHERE tour_plan_id IS NOT NULL)""",
        "dcr_call: one DCR submission per rep per day, after the day's last call":
            """SELECT COUNT(*) FROM (SELECT employee_id, call_date, COUNT(DISTINCT submitted_at) n,
                      MAX(call_date + call_start_time + INTERVAL (COALESCE(duration_minutes, 5)) MINUTE) last_end,
                      MIN(submitted_at) sub FROM dcr_call GROUP BY ALL) WHERE n > 1 OR sub < last_end""",
        "dcr_call: check-in location for every in-clinic visit (incl. doctor unavailable), none for phone/virtual":
            "SELECT COUNT(*) FROM dcr_call WHERE (call_type = 'in_clinic') <> (checkin_latitude IS NOT NULL)",

        # ---------------- phase 2
        "business_unit: SBUs used by geography and employee exist":
            """SELECT COUNT(*) FROM (SELECT business_unit_id FROM geography UNION SELECT business_unit_id FROM employee)
               WHERE business_unit_id NOT IN (SELECT business_unit_id FROM business_unit)""",
        "kpi_target: MCR and MVC for every calendar month, 90 until Mar 2025 then 95":
            """SELECT (SELECT COUNT(DISTINCT year_month) FROM calendar_day) * 2 - COUNT(*)
                    + COUNT(*) FILTER (WHERE target_value <> CASE WHEN year_month < 202504 THEN 90 ELSE 95 END)
               FROM kpi_target""",
        "clinic: every clinic referenced by calls and MCL exists and belongs to that doctor":
            """SELECT COUNT(*) FROM (SELECT doctor_id, clinic_id FROM dcr_call UNION SELECT doctor_id, clinic_id FROM mcl) x
               LEFT JOIN clinic c USING (clinic_id) WHERE c.doctor_id IS DISTINCT FROM x.doctor_id""",
        "clinic: most in-clinic calls fall in the doctor's OPD session (>= 75%)":
            """SELECT AVG(((c.call_start_time < TIME '14:00') = list_bool_or([o.start_time < TIME '14:00'
                       FOR o IN k.opd_schedule]))::INT) < 0.75
               FROM dcr_call c JOIN clinic k USING (clinic_id)
               WHERE c.call_type = 'in_clinic' AND c.call_status = 'completed' AND k.clinic_type = 'private_clinic'
                 AND len(list_distinct([o.start_time < TIME '14:00' FOR o IN k.opd_schedule])) = 1""",
        "tour_plan: every call's plan row exists for the same rep, doctor and date":
            """SELECT COUNT(*) FROM dcr_call c LEFT JOIN tour_plan t USING (tour_plan_id)
               WHERE c.tour_plan_id IS NOT NULL AND (t.employee_id IS DISTINCT FROM c.employee_id
                 OR t.doctor_id IS DISTINCT FROM c.doctor_id OR t.plan_date IS DISTINCT FROM c.call_date)""",
        "tour_plan: approver is the employee's manager":
            """SELECT COUNT(*) FROM tour_plan t WHERE approved_by IS NOT NULL AND NOT EXISTS (SELECT 1 FROM employee e
               WHERE e.employee_id = t.employee_id AND e.manager_employee_id = t.approved_by)""",
        "tour_plan: deviation rows have no calls that day; booked slots are in the future":
            f"""SELECT (SELECT COUNT(*) FROM tour_plan t WHERE is_deviation AND EXISTS (SELECT 1 FROM dcr_call c
                        WHERE c.employee_id = t.employee_id AND c.call_date = t.plan_date))
                    + (SELECT COUNT(*) FROM tour_plan WHERE source = 'booked_slot' AND plan_date <= DATE '{config.AS_OF_DATE}')""",
        "tour_plan: draft plans are not submitted; submitted ones not yet approved":
            """SELECT COUNT(*) FROM tour_plan WHERE (status = 'draft' AND submitted_at IS NOT NULL)
               OR (status = 'submitted' AND approved_by IS NOT NULL) OR (status = 'approved' AND approved_by IS NULL)""",
        "agent_action_log: targets exist":
            """SELECT COUNT(*) FROM agent_action_log a WHERE NOT (
                 (target_table = 'call_note' AND target_id IN (SELECT note_id FROM call_note))
              OR (target_table = 'tour_plan' AND target_id IN (SELECT tour_plan_id FROM tour_plan))
              OR (target_table = 'communication' AND target_id IN (SELECT communication_id FROM communication))
              OR (target_table = 'nba_recommendation' AND target_id IN (SELECT recommendation_id FROM nba_recommendation)))""",
        "agent_action_log: successful approval-required actions carry an approver":
            """SELECT COUNT(*) FROM agent_action_log WHERE approval_required AND outcome = 'success'
               AND (approved_by IS NULL OR approved_at IS NULL)""",
        # ---------------- phase 3
        "product: every brand / SKU used elsewhere exists":
            """SELECT COUNT(*) FROM (SELECT brand_code FROM rcpa_entry UNION SELECT brand_code FROM doctor_brand_plan
               UNION SELECT brand_code FROM dcr_call_product UNION SELECT brand_code FROM content)
               WHERE brand_code NOT IN (SELECT brand_code FROM product)""",
        "chemist: chemists linked in MCL and audited in RCPA exist in the right territory":
            """SELECT (SELECT COUNT(*) FROM (SELECT UNNEST(linked_chemist_ids) cid FROM mcl) WHERE cid NOT IN (SELECT chemist_id FROM chemist))
                    + (SELECT COUNT(*) FROM rcpa_entry r JOIN chemist c USING (chemist_id) JOIN geography g ON g.patch_id = c.patch_id
                       WHERE g.territory_id <> r.territory_id)""",
        "rcpa_entry: auditor was the territory's BO; working day; not after as-of":
            f"""SELECT COUNT(*) FROM rcpa_entry r WHERE r.audit_date > DATE '{config.AS_OF_DATE}' OR NOT EXISTS (
               SELECT 1 FROM employee e WHERE e.employee_id = r.employee_id AND e.territory_id = r.territory_id
               AND r.audit_date BETWEEN e.valid_from AND COALESCE(e.valid_to, DATE '9999-12-31'))
               OR EXTRACT(isodow FROM r.audit_date) = 7""",
        "rcpa_entry: value = strips x price; prescriptions positive":
            """SELECT COUNT(*) FROM rcpa_entry r JOIN (SELECT DISTINCT brand_code, price_per_strip_inr p FROM product
               WHERE is_own_brand = false OR sku_code IN (SELECT MIN(sku_code) FROM product GROUP BY brand_code)) x USING (brand_code)
               WHERE prescriptions <= 0 OR ABS(value_inr - quantity_strips * p) > 1""",
        "doctor_brand_plan: doctor on the MCL that month; targets only for focus brands":
            """SELECT COUNT(*) FROM doctor_brand_plan b WHERE (target_rx IS NOT NULL) <> is_focus_brand
               OR brand_priority <> 'P' || brand_rank OR NOT EXISTS (SELECT 1 FROM mcl m
               WHERE m.territory_id = b.territory_id AND m.doctor_id = b.doctor_id
                 AND make_date(b.year_month // 100, b.year_month % 100, 1) BETWEEN m.valid_from AND COALESCE(m.valid_to, DATE '9999-12-31'))""",
        "dcr_call_product: completed call; detailing within call length; samples sample-eligible SKUs of that brand":
            """SELECT (SELECT COUNT(*) FROM dcr_call_product p LEFT JOIN dcr_call c USING (call_id)
                       WHERE c.call_status IS DISTINCT FROM 'completed')
                    + (SELECT COUNT(*) FROM (SELECT call_id, SUM(detailing_seconds) s FROM dcr_call_product GROUP BY 1)
                       JOIN dcr_call USING (call_id) WHERE s > duration_minutes * 60)
                    + (SELECT COUNT(*) FROM dcr_call_product p LEFT JOIN product k USING (sku_code)
                       WHERE p.line_type = 'sample' AND (k.brand_code IS DISTINCT FROM p.brand_code OR NOT k.is_sample_eligible))""",
        "dcr_call_product: content shown was approved, unexpired and for that brand on the call date":
            """SELECT COUNT(*) FROM dcr_call_product p JOIN dcr_call c USING (call_id) JOIN content k USING (content_id)
               WHERE k.brand_code <> p.brand_code OR c.call_date NOT BETWEEN k.approved_on AND k.expires_on OR k.status = 'withdrawn'""",
        # ---------------- phase 4
        "content: active items are unexpired":
            f"SELECT COUNT(*) FROM content WHERE status = 'active' AND expires_on < DATE '{config.AS_OF_DATE}'",
        "formulary_listing: only hospitals; periods do not overlap":
            """SELECT (SELECT COUNT(*) FROM formulary_listing f JOIN clinic c USING (clinic_id) WHERE c.clinic_type <> 'hospital')
                    + (SELECT COUNT(*) FROM formulary_listing a JOIN formulary_listing b ON a.clinic_id = b.clinic_id
                       AND a.brand_code = b.brand_code AND a.listing_id < b.listing_id
                       AND a.effective_from <= COALESCE(b.effective_to, DATE '9999-12-31')
                       AND b.effective_from <= COALESCE(a.effective_to, DATE '9999-12-31'))""",
        "call_note: matches its call (rep, doctor), recorded after the call ends":
            """SELECT COUNT(*) FROM call_note n JOIN dcr_call c USING (call_id)
               WHERE n.employee_id <> c.employee_id OR n.doctor_id <> c.doctor_id
                  OR n.recorded_at < c.call_date + c.call_start_time + INTERVAL (c.duration_minutes) MINUTE""",
        "call_note: brands discussed were detailed in that call":
            """SELECT COUNT(*) FROM (SELECT note_id, call_id, UNNEST(brands_discussed) b FROM call_note) x
               WHERE NOT EXISTS (SELECT 1 FROM dcr_call_product p WHERE p.call_id = x.call_id AND p.brand_code = x.b
                                 AND p.line_type = 'detailing')""",
        "call_note: voice notes have audio; confirmed notes have confirmation time; voice only from pilot":
            f"""SELECT COUNT(*) FROM call_note WHERE (source = 'voice' AND audio_blob_path IS NULL)
               OR (status = 'confirmed' AND confirmed_at IS NULL)
               OR (source = 'voice' AND CAST(recorded_at AS DATE) < DATE '{config.PILOT_START}')""",
        "communication: outbound messages only to doctors who opted in on that channel":
            """SELECT COUNT(*) FROM communication m JOIN doctor d USING (doctor_id)
               WHERE m.direction = 'outbound' AND m.sent_at IS NOT NULL AND NOT (
                 (m.channel IN ('email', 'webinar') AND d.consent_email = 'opted_in')
              OR (m.channel = 'whatsapp' AND d.consent_whatsapp = 'opted_in'))""",
        "communication: agent messages sent only after rep approval; time order sent <= delivered <= opened":
            """SELECT COUNT(*) FROM communication WHERE (generated_by = 'agent' AND sent_at IS NOT NULL
                 AND (approved_at IS NULL OR approved_at > sent_at))
               OR delivered_at < sent_at OR opened_at < delivered_at OR responded_at < opened_at""",
        "all tables: no event timestamp after the snapshot load time":
            f"""SELECT COUNT(*) FROM (
                 SELECT submitted_at ts FROM dcr_call UNION ALL SELECT recorded_at FROM call_note
                 UNION ALL SELECT confirmed_at FROM call_note UNION ALL SELECT occurred_at FROM agent_action_log
                 UNION ALL SELECT approved_at FROM agent_action_log UNION ALL SELECT generated_at FROM nba_recommendation
                 UNION ALL SELECT status_at FROM nba_recommendation UNION ALL SELECT submitted_at FROM tour_plan
                 UNION ALL SELECT approved_at FROM tour_plan UNION ALL SELECT booking_confirmed_at FROM tour_plan
                 UNION ALL SELECT GREATEST(approved_at, sent_at, delivered_at, opened_at, clicked_at, responded_at)
                 FROM communication) WHERE ts >= TIMESTAMP '{config.LOAD_TS}'""",
        "nba_recommendation: from the pilot start; doctor practises in the rep's territory":
            f"""SELECT COUNT(*) FROM nba_recommendation n WHERE CAST(generated_at AS DATE) < DATE '{config.PILOT_START}'
               OR NOT EXISTS (SELECT 1 FROM clinic c JOIN geography g USING (patch_id)
                              WHERE c.doctor_id = n.doctor_id AND g.territory_id = n.territory_id)"""
    }
    present = {f.stem for f in P.glob("*.parquet")}
    import re
    checks = {k: v for k, v in checks.items()
              if set(re.findall(r"\b(?:FROM|JOIN)\s+([a-z_]+)", v)) <= present | {"x"}}
    failed = []
    for name, sql in checks.items():
        bad = _rows(con, sql)[0][0]
        ok = (bad == 0 or bad is False)
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  ({bad})"))
        if not ok:
            failed.append(name)
    if failed:
        raise SystemExit(f"{len(failed)} check(s) failed")


def kpi_report() -> None:
    """Monthly MCR / MVC / calls per day per territory (instrumentation)."""
    con = duckdb.connect()
    for t in ("mcl", "dcr_call", "employee"):
        con.execute(f"CREATE VIEW {t} AS SELECT * FROM '{P / (t + '.parquet')}'")
    df = con.execute("""
        WITH mo AS (SELECT DISTINCT DATE_TRUNC('month', call_date) AS mth FROM dcr_call),
        listed AS (SELECT mo.mth, l.territory_id, l.doctor_id, CAST(substr(l.visit_frequency, 2) AS INT) AS req
                   FROM mo JOIN mcl l ON l.valid_from <= mo.mth AND COALESCE(l.valid_to, DATE '9999-12-31') >= mo.mth),
        v AS (SELECT DATE_TRUNC('month', call_date) AS mth, territory_id, doctor_id, COUNT(*) AS n
              FROM dcr_call WHERE call_status = 'completed' GROUP BY ALL),
        cpd AS (SELECT DATE_TRUNC('month', call_date) AS mth, territory_id,
                COUNT(*) FILTER (WHERE call_status = 'completed') / COUNT(DISTINCT call_date) AS calls_per_day
                FROM dcr_call GROUP BY ALL)
        SELECT l.territory_id, strftime(l.mth, '%Y-%m') AS ym,
               ROUND(100 * AVG((v.n IS NOT NULL)::INT), 1) AS mcr_pct,
               ROUND(100 * AVG((COALESCE(v.n, 0) >= l.req)::INT), 1) AS mvc_pct,
               ROUND(ANY_VALUE(cpd.calls_per_day), 1) AS calls_per_day
        FROM listed l
        LEFT JOIN v ON v.mth = l.mth AND v.territory_id = l.territory_id AND v.doctor_id = l.doctor_id
        JOIN cpd ON cpd.mth = l.mth AND cpd.territory_id = l.territory_id
        GROUP BY ALL ORDER BY 1, 2""").df()
    df = df[df.ym < config.AS_OF_DATE.strftime("%Y-%m")]          # full months only
    print(df.groupby("territory_id")[["mcr_pct", "mvc_pct", "calls_per_day"]].mean().round(1).to_string())
    print("\nDelhi (handover) and Kolkata (declining), last 6 full months:")
    print(df[df.territory_id.isin([900003, 900005])].groupby("territory_id").tail(6).to_string(index=False))
