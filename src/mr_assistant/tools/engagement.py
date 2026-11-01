"""Engagement: call notes, samples, messages, channel response, best contact time, content, NBA,
and what changed since the last visit."""

from datetime import date, datetime

from mr_assistant.db import Db
from mr_assistant.tools._base import Out, as_of
from mr_assistant.tools.doctors import _visible
from mr_assistant.tools.planning import WEEKDAYS


class CallNote(Out):
    note_id: int
    call_id: int
    recorded_at: datetime
    author: str | None
    source: str
    status: str
    summary: str | None
    objections: str | None
    doctor_commitments: str | None
    rep_commitments: str | None
    next_step: str | None
    next_call_date: date | None
    doctor_receptivity: str | None
    compliance_flags: list[str] | None


class SampleSummary(Out):
    item_type: str
    item: str
    brand_name: str
    total_quantity: int
    times_given: int
    last_given: date


class Message(Out):
    communication_id: int
    channel: str
    direction: str
    generated_by: str
    status: str
    subject: str | None
    content_title: str | None
    sent_at: datetime | None
    opened_at: datetime | None
    responded_at: datetime | None
    response_type: str | None


class ChannelStats(Out):
    channel: str
    sent: int
    delivered: int
    opened: int
    responded: int
    open_rate_pct: float | None
    response_rate_pct: float | None


class ContactTime(Out):
    doctor_id: int
    completed_calls_analysed: int
    best_session: str | None
    morning_calls: int
    evening_calls: int
    best_weekdays: list[str]
    usual_message_open_hour: int | None
    rep_visit_hours: list[str]


class ContentItem(Out):
    content_id: int
    brand_code: str
    brand_name: str
    title: str
    content_type: str
    language: str
    target_specialties: list[str] | None
    key_message: str | None
    approved_on: date
    expires_on: date


class Recommendation(Out):
    recommendation_id: int
    generated_at: datetime
    doctor_id: int
    doctor_name: str
    action_type: str
    brand_name: str | None
    reason_codes: list[str]
    score: float
    status: str


class BrandChange(Out):
    brand_name: str
    rx_before: int | None
    rx_after: int | None


class WhatChanged(Out):
    doctor_id: int
    since: date | None
    days_since_last_visit: int | None
    own_rx_changes: list[BrandChange]
    formulary_changes: list[str]
    messages_sent: int
    responses: int
    new_notes: int


def get_call_notes(db: Db, doctor_id: int, limit: int = 5, include_drafts: bool = False) -> list[CallNote]:
    """Latest call notes for a doctor (newest first): summary, objections, commitments, next step.
    Only confirmed notes unless include_drafts=True."""
    _visible(db, doctor_id)
    rows = db.all("""
        SELECT note_id, call_id, recorded_at, analytics.employee_name(employee_id) AS author, source, status,
               summary, objections, doctor_commitments, rep_commitments, next_step, next_call_date,
               doctor_receptivity, compliance_flags
        FROM core.call_note
        WHERE doctor_id = %s AND (%s OR status = 'confirmed')
        ORDER BY recorded_at DESC LIMIT %s""", (doctor_id, include_drafts, limit))
    return [CallNote(**r) for r in rows]


def get_samples_given(db: Db, doctor_id: int, months: int = 3) -> list[SampleSummary]:
    """Samples and inputs given to a doctor in the last `months` months, totalled per item."""
    _visible(db, doctor_id)
    rows = db.all("""
        SELECT p.line_type AS item_type, COALESCE(pr.sku_name, p.input_description) AS item, b.brand_name,
               SUM(p.quantity)::int AS total_quantity, COUNT(*)::int AS times_given, MAX(c.call_date) AS last_given
        FROM core.dcr_call_product p
        JOIN core.dcr_call c USING (call_id)
        JOIN analytics.brand b USING (brand_code)
        LEFT JOIN core.product pr ON pr.sku_code = p.sku_code
        WHERE c.doctor_id = %s AND p.line_type IN ('sample', 'input')
          AND c.call_date > (SELECT analytics.as_of_date()) - make_interval(months => %s)
        GROUP BY 1, 2, 3 ORDER BY last_given DESC, item""", (doctor_id, months))
    return [SampleSummary(**r) for r in rows]


def get_communications(db: Db, doctor_id: int, limit: int = 10) -> list[Message]:
    """Latest messages with a doctor (email, WhatsApp, webinar invites; both directions) and the response."""
    _visible(db, doctor_id)
    rows = db.all("""
        SELECT m.communication_id, m.channel, m.direction, m.generated_by, m.status, m.subject,
               k.title AS content_title, m.sent_at, m.opened_at, m.responded_at, m.response_type
        FROM core.communication m LEFT JOIN core.content k USING (content_id)
        WHERE m.doctor_id = %s
        ORDER BY COALESCE(m.sent_at, m.approved_at, m.created_at) DESC LIMIT %s""", (doctor_id, limit))
    return [Message(**r) for r in rows]


def get_channel_effectiveness(db: Db, doctor_id: int | None = None, months: int = 6,
                              territory_id: int | None = None) -> list[ChannelStats]:
    """Open and response rates per channel over the last `months` months, for one doctor or your whole territory."""
    if doctor_id is not None:
        _visible(db, doctor_id)
    rows = db.all("""
        SELECT channel, COUNT(*)::int AS sent,
               COUNT(*) FILTER (WHERE status = 'delivered')::int AS delivered,
               COUNT(opened_at)::int AS opened, COUNT(responded_at)::int AS responded,
               ROUND(100.0 * COUNT(opened_at) / NULLIF(COUNT(*) FILTER (WHERE status = 'delivered'), 0), 1)::float AS open_rate_pct,
               ROUND(100.0 * COUNT(responded_at) / NULLIF(COUNT(*) FILTER (WHERE status = 'delivered'), 0), 1)::float AS response_rate_pct
        FROM core.communication
        WHERE direction = 'outbound' AND sent_at IS NOT NULL
          AND sent_at > (SELECT analytics.as_of_date()) - make_interval(months => %(m)s)
          AND (%(d)s::bigint IS NULL OR doctor_id = %(d)s)
          AND (%(terr)s::bigint IS NULL OR territory_id = %(terr)s)
        GROUP BY channel ORDER BY channel""", {"m": months, "d": doctor_id, "terr": territory_id})
    return [ChannelStats(**r) for r in rows]


def get_best_contact_time(db: Db, doctor_id: int) -> ContactTime:
    """When this doctor is usually met and reads messages: morning vs evening calls, best weekdays,
    usual message-open hour, and the clinic's rep-visit hours."""
    _visible(db, doctor_id)
    calls = db.one("""
        SELECT COUNT(*)::int AS n,
               COUNT(*) FILTER (WHERE call_start_time < '14:00')::int AS morning,
               COUNT(*) FILTER (WHERE call_start_time >= '14:00')::int AS evening
        FROM core.dcr_call WHERE doctor_id = %s AND call_status = 'completed'""", (doctor_id,))
    days = db.all("""SELECT EXTRACT(ISODOW FROM call_date)::int AS wd, COUNT(*) AS n FROM core.dcr_call
                     WHERE doctor_id = %s AND call_status = 'completed' GROUP BY 1 ORDER BY n DESC, wd LIMIT 2""",
                  (doctor_id,))
    open_hour = db.scalar("""SELECT MODE() WITHIN GROUP (ORDER BY EXTRACT(HOUR FROM opened_at AT TIME ZONE 'Asia/Kolkata'))::int
                             FROM core.communication WHERE doctor_id = %s AND opened_at IS NOT NULL""", (doctor_id,))
    windows = db.all("""SELECT DISTINCT to_char((w->>'start_time')::time, 'HH24:MI') || '-' ||
                               to_char((w->>'end_time')::time, 'HH24:MI') AS hrs
                        FROM core.clinic c, jsonb_array_elements(c.rep_visit_window) w
                        WHERE c.doctor_id = %s AND c.is_primary ORDER BY 1""", (doctor_id,))
    best = None
    if calls["n"]:
        best = "morning" if calls["morning"] >= calls["evening"] else "evening"
    return ContactTime(doctor_id=doctor_id, completed_calls_analysed=calls["n"], best_session=best,
                       morning_calls=calls["morning"], evening_calls=calls["evening"],
                       best_weekdays=[WEEKDAYS[d["wd"]] for d in days], usual_message_open_hour=open_hour,
                       rep_visit_hours=[w["hrs"] for w in windows])


def get_content(db: Db, brand_code: str | None = None, content_type: str | None = None,
                specialty: str | None = None, on_date: date | None = None) -> list[ContentItem]:
    """Approved content valid on a date (default: today in the data): visual aids, leaflets, study
    summaries, email and WhatsApp templates. Only this content may be shown or sent to doctors."""
    rows = db.all("""
        SELECT k.content_id, k.brand_code, b.brand_name, k.title, k.content_type, k.language,
               k.target_specialties, k.key_message, k.approved_on, k.expires_on
        FROM core.content k JOIN analytics.brand b USING (brand_code)
        WHERE k.status <> 'withdrawn'
          AND COALESCE(%(d)s::date, (SELECT analytics.as_of_date())) BETWEEN k.approved_on AND k.expires_on
          AND (%(b)s::text IS NULL OR k.brand_code = %(b)s)
          AND (%(t)s::text IS NULL OR k.content_type = %(t)s)
          AND (%(s)s::text IS NULL OR %(s)s = ANY (k.target_specialties))
        ORDER BY b.brand_name, k.content_type, k.title""",
        {"d": on_date, "b": brand_code, "t": content_type, "s": specialty})
    return [ContentItem(**r) for r in rows]


def get_nba_recommendations(db: Db, on_date: date | None = None, status: str | None = None,
                            limit: int = 20) -> list[Recommendation]:
    """Next-best-action recommendations generated on a date (default: the latest day), highest score first."""
    rows = db.all("""
        SELECT n.recommendation_id, n.generated_at, n.doctor_id, d.full_name AS doctor_name, n.action_type,
               b.brand_name, n.reason_codes, n.score, n.status
        FROM core.nba_recommendation n
        JOIN core.doctor d USING (doctor_id)
        LEFT JOIN analytics.brand b USING (brand_code)
        WHERE n.generated_at::date = COALESCE(%(d)s::date, (SELECT MAX(generated_at)::date FROM core.nba_recommendation))
          AND (%(s)s::text IS NULL OR n.status = %(s)s)
        ORDER BY n.score DESC, d.full_name LIMIT %(limit)s""", {"d": on_date, "s": status, "limit": limit})
    return [Recommendation(**r) for r in rows]


def get_what_changed(db: Db, doctor_id: int) -> WhatChanged:
    """What changed for a doctor since the last completed visit: own-brand Rx in audits before vs after,
    formulary changes, messages and responses, and new notes."""
    _visible(db, doctor_id)
    since = db.scalar("""SELECT MAX(call_date) FROM core.dcr_call
                         WHERE doctor_id = %s AND call_status = 'completed'""", (doctor_id,))
    today = as_of(db)
    if since is None:
        return WhatChanged(doctor_id=doctor_id, since=None, days_since_last_visit=None, own_rx_changes=[],
                           formulary_changes=[], messages_sent=0, responses=0, new_notes=0)
    changes = db.all("""
        SELECT b.brand_name,
               (SELECT SUM(r.prescriptions) FROM core.rcpa_entry r WHERE r.doctor_id = %(d)s AND r.brand_code = b.brand_code
                  AND r.audit_date = (SELECT MAX(audit_date) FROM core.rcpa_entry
                                      WHERE doctor_id = %(d)s AND brand_code = b.brand_code AND audit_date <= %(since)s))::int AS rx_before,
               (SELECT SUM(r.prescriptions) FROM core.rcpa_entry r WHERE r.doctor_id = %(d)s AND r.brand_code = b.brand_code
                  AND r.audit_date = (SELECT MAX(audit_date) FROM core.rcpa_entry
                                      WHERE doctor_id = %(d)s AND brand_code = b.brand_code AND audit_date > %(since)s))::int AS rx_after
        FROM analytics.brand b
        WHERE b.is_own_brand AND EXISTS (SELECT 1 FROM core.rcpa_entry r WHERE r.doctor_id = %(d)s AND r.brand_code = b.brand_code)
        ORDER BY b.brand_name""", {"d": doctor_id, "since": since})
    formulary = db.all("""
        SELECT c.clinic_name || ': ' || b.brand_name || ' ' || replace(f.listing_status, '_', ' ')
               || ' from ' || to_char(f.effective_from, 'DD Mon YYYY') AS change
        FROM core.formulary_listing f JOIN core.clinic c USING (clinic_id) JOIN analytics.brand b USING (brand_code)
        WHERE c.doctor_id = %s AND f.effective_from > %s ORDER BY f.effective_from""", (doctor_id, since))
    msgs = db.one("""SELECT COUNT(*) FILTER (WHERE direction = 'outbound' AND sent_at IS NOT NULL)::int AS sent,
                            COUNT(responded_at)::int AS responded
                     FROM core.communication WHERE doctor_id = %s AND sent_at > %s""", (doctor_id, since))
    notes = db.scalar("""SELECT COUNT(*)::int FROM core.call_note n JOIN core.dcr_call c USING (call_id)
                         WHERE n.doctor_id = %s AND c.call_date > %s""", (doctor_id, since))
    return WhatChanged(doctor_id=doctor_id, since=since, days_since_last_visit=(today - since).days,
                       own_rx_changes=[BrandChange(**c) for c in changes if c["rx_after"] is not None],
                       formulary_changes=[f["change"] for f in formulary], messages_sent=msgs["sent"],
                       responses=msgs["responded"], new_notes=notes)
