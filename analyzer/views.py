import datetime
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from .models import QCEntry
from .services.analyzer_reader import check_connection, get_state, start_reading, stop_reading
from .services.sync_service import fetch_local_rows, server_available, sync_local_to_server


def _current_shift(now=None):
    now = now or datetime.datetime.now()
    return "AM" if now.hour < 12 else "PM"


def dashboard(request):
    if request.method == "POST":
        date_value = (request.POST.get("date") or "").strip()
        shift = (request.POST.get("shift") or "AM").upper()

        samples = request.POST.getlist("sample_code[]")
        fats = request.POST.getlist("fat[]")
        snfs = request.POST.getlist("snf[]")
        clrs = request.POST.getlist("clr[]")

        if not date_value:
            messages.error(request, "Date is required.")
            return redirect("dashboard")

        if not (len(samples) == len(fats) == len(snfs) == len(clrs)):
            messages.error(request, "Batch row data mismatch.")
            return redirect("dashboard")

        if not samples:
            messages.error(request, "Add at least one QC row.")
            return redirect("dashboard")

        saved = 0
        try:
            with transaction.atomic():
                for i in range(len(samples)):
                    sample = int(samples[i])
                    fat = Decimal(fats[i])
                    snf = Decimal(snfs[i])
                    clr = Decimal(clrs[i])

                    row = QCEntry(
                        date=date_value,
                        shift=shift,
                        sample_code=sample,
                        fat=fat,
                        snf=snf,
                        clr=clr,
                        analyzer_code="Analyzer01",
                    )
                    row.full_clean()
                    row.save()
                    saved += 1

        except (ValueError, InvalidOperation):
            messages.error(request, "One or more QC values are invalid.")
            return redirect("dashboard")
        except IntegrityError:
            messages.error(request, "A duplicate sample already exists for this date and shift.")
            return redirect("dashboard")
        except Exception as exc:
            messages.error(request, str(exc))
            return redirect("dashboard")

        messages.success(request, f"Saved {saved} QC entr{'y' if saved == 1 else 'ies'} successfully.")
        return redirect("dashboard")

    return render(
        request,
        "analyzer/dashboard.html",
        {
            "today": datetime.date.today().isoformat(),
            "current_shift": _current_shift(),
            "mode": settings.ANALYZER_MODE,
        },
    )


@require_GET
def analyzer_connect(request):
    ok, message = check_connection()
    return JsonResponse({"ok": ok, "message": message, "state": get_state()})


@require_POST
def analyzer_start(request):
    ok, message = start_reading()
    return JsonResponse({"ok": ok, "message": message, "state": get_state()})


@require_POST
def analyzer_stop(request):
    ok, message = stop_reading()
    return JsonResponse({"ok": ok, "message": message, "state": get_state()})


@require_GET
def analyzer_status(request):
    return JsonResponse(get_state())


@require_POST
def validate_sample(request):
    date_value = (request.POST.get("date") or "").strip()
    shift = (request.POST.get("shift") or "AM").upper()
    sample_raw = (request.POST.get("sample_code") or "").strip()

    try:
        sample_code = int(sample_raw)
    except ValueError:
        return JsonResponse({"valid": False, "message": "Enter a valid sample number."})

    exists = QCEntry.objects.filter(
        date=date_value,
        shift=shift,
        sample_code=sample_code,
    ).exists()

    if exists:
        return JsonResponse({"valid": False, "message": "Duplicate sample number exists in database."})

    return JsonResponse({"valid": True})


def records(request):
    rows = QCEntry.objects.all()[:250]
    return render(request, "analyzer/records.html", {"rows": rows})


def summary(request):
    date_value = (request.GET.get("date") or "").strip()
    shift = (request.GET.get("shift") or "ALL").upper()

    qs = QCEntry.objects.all()
    searched = bool(date_value)

    if date_value:
        qs = qs.filter(date=date_value)
    if shift in {"AM", "PM"}:
        qs = qs.filter(shift=shift)

    agg = qs.aggregate(
        total=Count("id"),
        avg_fat=Avg("fat"),
        avg_snf=Avg("snf"),
        avg_clr=Avg("clr"),
    )

    return render(
        request,
        "analyzer/summary.html",
        {
            "date_value": date_value,
            "shift": shift,
            "searched": searched,
            "total": agg["total"] or 0,
            "avg_fat": round(float(agg["avg_fat"] or 0), 2),
            "avg_snf": round(float(agg["avg_snf"] or 0), 2),
            "avg_clr": round(float(agg["avg_clr"] or 0), 2),
        },
    )


def server_sync(request):
    """
    Portfolio equivalent of the original Analyzer Server Connectivity screen:
    select date + shift, preview local analyzer rows, and apply them to server.
    """
    today = datetime.date.today().isoformat()
    date_value = (request.POST.get("date") or request.GET.get("date") or today).strip()
    shift = (request.POST.get("shift") or request.GET.get("shift") or _current_shift()).upper()
    action = (request.POST.get("action") or "").strip()

    analyzer_rows = []
    fetched = False

    if request.method == "POST":
        if action == "fetch":
            fetched = True
            analyzer_rows = fetch_local_rows(date_value, shift)

        elif action == "apply_to_server":
            result = sync_local_to_server(date_value, shift)

            if result["ok"]:
                messages.success(
                    request,
                    f"Sent {result['pushed']} QC record(s) to server and removed "
                    f"{result['deleted']} synchronized local row(s)."
                )
            else:
                messages.error(request, f"Server sync failed: {result['error']}")

            return redirect(f"/server-sync/?date={date_value}&shift={shift}")

    elif date_value:
        # Keep GET lightweight but useful after redirect.
        analyzer_rows = fetch_local_rows(date_value, shift)
        fetched = True

    server_ok, server_error = server_available()
    local_pending = QCEntry.objects.using("default").filter(
        date=date_value,
        shift__iexact=shift,
    ).count()

    try:
        server_count = QCEntry.objects.using("server").filter(
            date=date_value,
            shift__iexact=shift,
        ).count()
    except Exception:
        server_count = 0

    return render(
        request,
        "analyzer/server_sync.html",
        {
            "date_value": date_value,
            "shift": shift,
            "fetched": fetched,
            "analyzer_rows": analyzer_rows,
            "server_ok": server_ok,
            "server_error": server_error,
            "local_pending": local_pending,
            "server_count": server_count,
        },
    )


@require_GET
def server_status(request):
    ok, error = server_available()
    return JsonResponse({
        "status": "UP" if ok else "DOWN",
        "ok": ok,
        "error": error,
        "database": "server",
    })
