from django.db import connections, transaction

from analyzer.models import QCEntry


def server_available():
    """Return whether the configured server database is reachable."""
    try:
        with connections["server"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True, ""
    except Exception as exc:
        return False, str(exc)


def fetch_local_rows(date_value, shift):
    """Preview local QC rows for the selected date and shift."""
    qs = QCEntry.objects.using("default").filter(date=date_value)

    if shift and shift.upper() in {"AM", "PM"}:
        qs = qs.filter(shift__iexact=shift)

    # sample_code is numeric in this sanitized project, so normal ordering is safe.
    return list(qs.order_by("sample_code", "id"))


def sync_local_to_server(date_value, shift):
    """
    Push unique local QC samples to the server database.

    Flow:
    1. Check server DB connection.
    2. Fetch local rows for date + shift.
    3. De-duplicate by sample_code.
    4. update_or_create on server for retry safety.
    5. Delete ONLY successfully pushed local rows.
    """
    ok, error = server_available()
    if not ok:
        return {
            "ok": False,
            "pushed": 0,
            "deleted": 0,
            "error": error,
        }

    local_rows = fetch_local_rows(date_value, shift)

    seen_samples = set()
    unique_rows = []
    for row in local_rows:
        if row.sample_code in seen_samples:
            continue
        seen_samples.add(row.sample_code)
        unique_rows.append(row)

    pushed_ids = []
    pushed = 0

    try:
        for row in unique_rows:
            QCEntry.objects.using("server").update_or_create(
                date=row.date,
                shift=row.shift,
                sample_code=row.sample_code,
                defaults={
                    "fat": row.fat,
                    "snf": row.snf,
                    "clr": row.clr,
                    "analyzer_code": row.analyzer_code,
                },
            )
            pushed_ids.append(row.id)
            pushed += 1

    except Exception as exc:
        # Keep any not-yet-confirmed local rows. Successfully pushed rows are
        # deliberately not removed if the overall operation reports an error.
        return {
            "ok": False,
            "pushed": pushed,
            "deleted": 0,
            "error": str(exc),
        }

    deleted = 0
    if pushed_ids:
        with transaction.atomic(using="default"):
            qs = QCEntry.objects.using("default").filter(id__in=pushed_ids)
            deleted = qs.count()
            qs.delete()

    return {
        "ok": True,
        "pushed": pushed,
        "deleted": deleted,
        "error": "",
    }
