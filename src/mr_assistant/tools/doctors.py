"""Doctors: search, profile, lists, clinics and the Doctor 360 view."""

import re
from datetime import date, time

from mr_assistant.db import Db
from mr_assistant.errors import NotFound, ToolError
from mr_assistant.tools._base import Out


class DoctorMatch(Out):
    doctor_id: int
    doctor_code: str
    full_name: str
    specialty: str
    territory_id: int | None
    doctor_class: str | None
    city: str | None
    similarity: float


class DoctorProfile(Out):
    doctor_id: int
    doctor_code: str
    full_name: str
    gender: str | None
    qualification: str | None
    specialty: str
    years_of_practice: int | None
    registration_no: str | None
    mobile: str | None
    email: str | None
    territory_id: int | None
    doctor_class: str | None
    visit_frequency: str | None
    primary_clinic: str | None
    clinic_address: str | None
    city: str | None
    prescriber_persona: str | None
    behavioural_persona: str | None
    loyalty_persona: str | None
    digital_persona: str | None
    in_clinic_engagement: bool
    patient_support: bool
    scientific_engagement: bool
    academy_member: bool
    digital_connect_member: bool
    patient_program_user: bool
    consent_email: str
    consent_whatsapp: str
    consent_sms: str
    consent_phone: str
    public_bio: str | None
    recent_public_topics: list[str] | None
    social_compliance_approved: bool | None


class DoctorListItem(Out):
    doctor_id: int
    doctor_code: str
    full_name: str
    specialty: str
    doctor_class: str
    visit_frequency: str
    territory_id: int
    patch_name: str
    city: str


class TimeWindow(Out):
    weekday: int
    start_time: time
    end_time: time


class ClinicInfo(Out):
    clinic_id: int
    clinic_name: str
    clinic_type: str
    is_primary: bool
    address: str
    city: str
    opd_schedule: list[TimeWindow]
    rep_visit_window: list[TimeWindow]


class Doctor360(Out):
    doctor_id: int
    doctor_code: str
    full_name: str
    specialty: str
    qualification: str | None
    years_of_practice: int | None
    territory_id: int
    doctor_class: str
    visit_frequency: str
    primary_clinic: str | None
    primary_clinic_type: str | None
    city: str | None
    visits_done_this_month: int | None
    visits_required_this_month: int | None
    visits_pending_this_month: int | None
    last_visit_date: date | None
    days_since_last_visit: int | None
    own_rx_3m: int | None
    total_rx_3m: int | None
    own_share_3m_pct: float | None
    own_rx_prev_3m: int | None
    own_rx_trend_pct: float | None
    last_note_date: date | None
    last_note_summary: str | None
    last_note_objections: str | None
    last_receptivity: str | None
    prescriber_persona: str | None
    behavioural_persona: str | None
    loyalty_persona: str | None
    digital_persona: str | None
    consent_email: str
    consent_whatsapp: str
    whatsapp_messages_90d: int | None
    whatsapp_responses_90d: int | None


def _visible(db: Db, doctor_id: int) -> None:
    if db.scalar("SELECT 1 FROM core.doctor WHERE doctor_id = %s", (doctor_id,)) is None:
        raise NotFound(f"Doctor {doctor_id} not found in your territory.")


def find_doctor(db: Db, query: str, limit: int = 5) -> list[DoctorMatch]:
    """Find doctors by name (fuzzy, typo-tolerant) or by doctor code. Searches only your territory.

    Use this first whenever the user mentions a doctor by name, e.g. "Dr Rao" or "Karthik Raghavan".
    """
    q = re.sub(r"^\s*dr\.?\s+", "", query.strip(), flags=re.IGNORECASE)
    if not q:
        raise ToolError("Give a doctor name or code to search for.")
    rows = db.all("""
        SELECT d.doctor_id, d.doctor_code, d.full_name, d.specialty, m.territory_id, m.doctor_class, c.city,
               ROUND(GREATEST(similarity(d.full_name, %(q)s), word_similarity(%(q)s, d.full_name),
                              CASE WHEN d.doctor_code = %(q)s THEN 1 ELSE 0 END)::numeric, 3)::float AS similarity
        FROM core.doctor d
        LEFT JOIN core.mcl m ON m.doctor_id = d.doctor_id AND m.is_current
        LEFT JOIN core.clinic c ON c.doctor_id = d.doctor_id AND c.is_primary
        WHERE d.mdm_status = 'active'
          AND (d.doctor_code = %(q)s OR d.full_name %% %(q)s OR %(q)s <%% d.full_name)
        ORDER BY similarity DESC, d.full_name
        LIMIT %(limit)s""", {"q": q, "limit": limit})
    return [DoctorMatch(**r) for r in rows]


def get_doctor_profile(db: Db, doctor_id: int) -> DoctorProfile:
    """Full profile of one doctor: qualification, contact, personas, engagement flags, consent, clinic."""
    r = db.one("""
        SELECT d.*, m.territory_id, m.doctor_class, m.visit_frequency,
               c.clinic_name AS primary_clinic, c.address AS clinic_address, c.city
        FROM core.doctor d
        LEFT JOIN core.mcl m ON m.doctor_id = d.doctor_id AND m.is_current
        LEFT JOIN core.clinic c ON c.doctor_id = d.doctor_id AND c.is_primary
        WHERE d.doctor_id = %s""", (doctor_id,))
    if r is None:
        raise NotFound(f"Doctor {doctor_id} not found in your territory.")
    return DoctorProfile(**{k: r[k] for k in DoctorProfile.model_fields})


def list_doctors(db: Db, doctor_class: str | None = None, specialty: str | None = None,
                 patch_id: int | None = None, territory_id: int | None = None,
                 limit: int = 200) -> list[DoctorListItem]:
    """Doctors on your current call list (MCL), optionally filtered by class (A/B/C), specialty or patch."""
    rows = db.all("""
        SELECT d.doctor_id, d.doctor_code, d.full_name, d.specialty, m.doctor_class, m.visit_frequency,
               m.territory_id, g.patch_name, g.city
        FROM core.mcl m
        JOIN core.doctor d USING (doctor_id)
        JOIN core.geography g ON g.patch_id = m.patch_id
        WHERE m.is_current
          AND (%(cls)s::text IS NULL OR m.doctor_class = %(cls)s)
          AND (%(spec)s::text IS NULL OR d.specialty ILIKE %(spec)s)
          AND (%(patch)s::bigint IS NULL OR m.patch_id = %(patch)s)
          AND (%(terr)s::bigint IS NULL OR m.territory_id = %(terr)s)
        ORDER BY m.doctor_class, d.full_name
        LIMIT %(limit)s""",
        {"cls": doctor_class, "spec": specialty, "patch": patch_id, "terr": territory_id, "limit": limit})
    return [DoctorListItem(**r) for r in rows]


def get_doctor_clinics(db: Db, doctor_id: int) -> list[ClinicInfo]:
    """Where a doctor practises, with OPD hours and the times reps are usually seen."""
    _visible(db, doctor_id)
    rows = db.all("""SELECT clinic_id, clinic_name, clinic_type, is_primary, address, city, opd_schedule, rep_visit_window
                     FROM core.clinic WHERE doctor_id = %s ORDER BY is_primary DESC, clinic_id""", (doctor_id,))
    return [ClinicInfo(**r) for r in rows]


def get_doctor_360(db: Db, doctor_id: int) -> Doctor360:
    """Everything about one doctor in one call: class, this month's visits, 3-month own-brand Rx, share and
    trend, latest confirmed note (summary, objections, receptivity), personas, consent, WhatsApp response."""
    r = db.one("SELECT * FROM analytics.doctor_360 WHERE doctor_id = %s", (doctor_id,))
    if r is None:
        raise NotFound(f"Doctor {doctor_id} is not on a current call list in your territory.")
    return Doctor360(**{k: r[k] for k in Doctor360.model_fields})
