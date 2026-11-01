"""Market: prescriptions (RCPA), share, brand performance vs target, products to detail, formulary, catalog."""

from datetime import date

from mr_assistant.db import Db
from mr_assistant.errors import NotFound
from mr_assistant.tools._base import Out, month_or_current
from mr_assistant.tools.doctors import _visible


class BrandRx(Out):
    year_month: int
    brand_code: str
    brand_name: str
    is_own_brand: bool
    molecule_class: str
    prescriptions: int
    value_inr: float


class MarketShareRow(Out):
    year_month: int
    territory_id: int
    molecule_class: str
    therapy_area: str
    own_rx: int | None
    competitor_rx: int | None
    total_rx: int
    own_share_pct: float | None


class BrandPerformance(Out):
    year_month: int
    territory_id: int
    brand_code: str
    brand_name: str
    audited_doctors: int
    own_rx: int
    target_rx: float | None
    achievement_pct: float | None
    own_value_inr: float


class ProductToDetail(Out):
    brand_code: str
    brand_name: str
    brand_priority: str
    brand_rank: int
    is_focus_brand: bool
    is_growth_brand: bool
    potential_rx: float
    target_rx: float | None
    last_audited_rx: int | None
    last_audit_month: int | None


class RxDecliner(Out):
    doctor_id: int
    doctor_name: str
    territory_id: int
    doctor_class: str
    own_rx_3m: int | None
    own_rx_prev_3m: int | None
    own_rx_trend_pct: float | None
    last_receptivity: str | None
    last_note_objections: str | None


class FormularyStatus(Out):
    clinic_name: str
    brand_code: str
    brand_name: str
    listing_status: str
    effective_from: date
    effective_to: date | None
    notes: str | None


class ProductInfo(Out):
    sku_code: str
    sku_name: str
    brand_code: str
    brand_name: str
    dosage_form: str | None
    pack_size: str | None
    therapy_area: str
    molecule_class: str
    is_growth_brand: bool
    is_device: bool
    is_sample_eligible: bool
    price_per_strip_inr: float


def get_doctor_rx(db: Db, doctor_id: int, months: int = 6) -> list[BrandRx]:
    """Audited prescriptions (RCPA) by brand and month for one doctor over the last `months` months,
    own brands and competitors. Months without an audit have no rows."""
    _visible(db, doctor_id)
    rows = db.all("""
        SELECT year_month, brand_code, brand_name, is_own_brand, molecule_class, prescriptions, value_inr::float
        FROM analytics.rx_monthly
        WHERE doctor_id = %s AND year_month > analytics.ym_add((SELECT analytics.ym_of(analytics.as_of_date())), -%s)
        ORDER BY year_month, is_own_brand DESC, prescriptions DESC""", (doctor_id, months))
    return [BrandRx(**r) for r in rows]


def get_market_share(db: Db, year_month: int | None = None, months: int = 1, molecule_class: str | None = None,
                     territory_id: int | None = None) -> list[MarketShareRow]:
    """Own-brand share of audited prescriptions per therapy class and territory, for one month
    (default: current) or the `months` months ending there."""
    ym = month_or_current(db, year_month)
    rows = db.all("""
        SELECT year_month, territory_id, molecule_class, therapy_area, own_rx, competitor_rx, total_rx, own_share_pct::float
        FROM analytics.market_share
        WHERE year_month > analytics.ym_add(%(ym)s, -%(m)s) AND year_month <= %(ym)s
          AND (%(cls)s::text IS NULL OR molecule_class = %(cls)s)
          AND (%(terr)s::bigint IS NULL OR territory_id = %(terr)s)
        ORDER BY territory_id, molecule_class, year_month""",
        {"ym": ym, "m": months, "cls": molecule_class, "terr": territory_id})
    return [MarketShareRow(**r) for r in rows]


def get_brand_performance(db: Db, year_month: int | None = None, territory_id: int | None = None) -> list[BrandPerformance]:
    """Own brands for a month (default: current): audited prescriptions vs target, over the doctors audited
    that month (RCPA is a sample, so achievement is measured on audited doctors only)."""
    ym = month_or_current(db, year_month)
    rows = db.all("""
        SELECT r.year_month, r.territory_id, r.brand_code, r.brand_name,
               COUNT(DISTINCT r.doctor_id) AS audited_doctors, SUM(r.prescriptions)::int AS own_rx,
               ROUND(SUM(p.target_rx)::numeric, 1)::float AS target_rx,
               ROUND(100.0 * SUM(r.prescriptions) FILTER (WHERE p.target_rx IS NOT NULL)
                     / NULLIF(SUM(p.target_rx), 0)::numeric, 1)::float AS achievement_pct,
               SUM(r.value_inr)::float AS own_value_inr
        FROM analytics.rx_monthly r
        LEFT JOIN core.doctor_brand_plan p
               ON p.doctor_id = r.doctor_id AND p.brand_code = r.brand_code
              AND p.year_month = r.year_month AND p.territory_id = r.territory_id
        WHERE r.is_own_brand AND r.year_month = %(ym)s
          AND (%(terr)s::bigint IS NULL OR r.territory_id = %(terr)s)
        GROUP BY 1, 2, 3, 4
        ORDER BY r.territory_id, own_rx DESC""", {"ym": ym, "terr": territory_id})
    return [BrandPerformance(**r) for r in rows]


def get_products_to_detail(db: Db, doctor_id: int, year_month: int | None = None) -> list[ProductToDetail]:
    """Brands to detail to a doctor, in priority order (P1 first), with potential, target and the latest
    audited prescriptions in the last 3 months."""
    _visible(db, doctor_id)
    ym = month_or_current(db, year_month)
    rows = db.all("""
        SELECT p.brand_code, b.brand_name, p.brand_priority, p.brand_rank, p.is_focus_brand, b.is_growth_brand,
               p.potential_rx, p.target_rx, last.prescriptions AS last_audited_rx, last.year_month AS last_audit_month
        FROM core.doctor_brand_plan p
        JOIN analytics.brand b USING (brand_code)
        LEFT JOIN LATERAL (
            SELECT r.prescriptions, r.year_month FROM analytics.rx_monthly r
            WHERE r.doctor_id = p.doctor_id AND r.brand_code = p.brand_code
              AND r.year_month BETWEEN analytics.ym_add(%(ym)s, -2) AND %(ym)s
            ORDER BY r.year_month DESC LIMIT 1) last ON true
        WHERE p.doctor_id = %(d)s
          AND p.year_month = (SELECT MAX(year_month) FROM core.doctor_brand_plan
                              WHERE doctor_id = %(d)s AND year_month <= %(ym)s)
        ORDER BY p.brand_rank""", {"d": doctor_id, "ym": ym})
    return [ProductToDetail(**r) for r in rows]


def get_rx_decliners(db: Db, min_drop_pct: float = 25, min_prev_rx: int = 10, limit: int = 10,
                     territory_id: int | None = None) -> list[RxDecliner]:
    """Doctors whose own-brand prescriptions fell the most (last 3 months vs the 3 before), with the
    latest note's receptivity and objections, which often explain why."""
    rows = db.all("""
        SELECT doctor_id, full_name AS doctor_name, territory_id, doctor_class, own_rx_3m, own_rx_prev_3m,
               own_rx_trend_pct::float, last_receptivity, last_note_objections
        FROM analytics.doctor_360
        WHERE own_rx_trend_pct <= -%(drop)s AND own_rx_prev_3m >= %(prev)s
          AND (%(terr)s::bigint IS NULL OR territory_id = %(terr)s)
        ORDER BY own_rx_trend_pct, own_rx_prev_3m DESC LIMIT %(limit)s""",
        {"drop": min_drop_pct, "prev": min_prev_rx, "terr": territory_id, "limit": limit})
    return [RxDecliner(**r) for r in rows]


def get_formulary_status(db: Db, doctor_id: int, include_history: bool = False) -> list[FormularyStatus]:
    """Brand listings in the hospitals where a doctor practises (current only, or full history)."""
    _visible(db, doctor_id)
    rows = db.all("""
        SELECT c.clinic_name, f.brand_code, b.brand_name, f.listing_status, f.effective_from, f.effective_to, f.notes
        FROM core.formulary_listing f
        JOIN core.clinic c USING (clinic_id)
        JOIN analytics.brand b USING (brand_code)
        WHERE c.doctor_id = %s AND (%s OR f.effective_to IS NULL)
        ORDER BY c.clinic_name, b.brand_name, f.effective_from""", (doctor_id, include_history))
    return [FormularyStatus(**r) for r in rows]


def list_products(db: Db, therapy_area: str | None = None, own_only: bool = True,
                  business_unit_id: int | None = None) -> list[ProductInfo]:
    """Product catalog (SKUs): brand, form, pack, class, growth-brand and sample flags, price."""
    rows = db.all("""
        SELECT sku_code, sku_name, brand_code, brand_name, dosage_form, pack_size, therapy_area, molecule_class,
               is_growth_brand, is_device, is_sample_eligible, price_per_strip_inr::float
        FROM core.product
        WHERE (NOT %(own)s OR is_own_brand)
          AND (%(ta)s::text IS NULL OR therapy_area ILIKE %(ta)s)
          AND (%(bu)s::bigint IS NULL OR business_unit_id = %(bu)s)
        ORDER BY brand_name, sku_code""", {"own": own_only, "ta": therapy_area, "bu": business_unit_id})
    return [ProductInfo(**r) for r in rows]
