import random
import re
import threading
import time
from dataclasses import dataclass

from django.conf import settings

FAT_PATTERN = re.compile(r"FAT[:=\s]+([0-9]+(?:\.[0-9]+)?)", re.I)
SNF_PATTERN = re.compile(r"SNF[:=\s]+([0-9]+(?:\.[0-9]+)?)", re.I)

_state_lock = threading.Lock()
_worker_lock = threading.Lock()
_stop_event = threading.Event()
_worker = None

STATE = {
    "connected": False,
    "reading_active": False,
    "status": "idle",
    "message": "Ready",
    "fat": None,
    "snf": None,
    "clr": None,
    "port": None,
    "baud": None,
    "last_error": None,
    "last_raw_text": "",
    "last_update_time": None,
}


def calculate_clr(fat, snf):
    return round(4 * (float(snf) - (0.21 * float(fat)) - 0.36), 2)


def parse_text(text):
    if not text:
        return None

    fat_match = FAT_PATTERN.search(text)
    snf_match = SNF_PATTERN.search(text)

    if fat_match and snf_match:
        fat = float(fat_match.group(1))
        snf = float(snf_match.group(1))
        if 0 <= fat <= 15 and 0 <= snf <= 20:
            return fat, snf

    # Fallback for simple "4.50 8.60" style output.
    for line in reversed(text.splitlines()):
        nums = re.findall(r"\d+(?:\.\d+)?", line)
        if len(nums) >= 2:
            fat = float(nums[0])
            snf = float(nums[1])
            if 0 <= fat <= 15 and 0 <= snf <= 20:
                return fat, snf

    return None


def _set(**kwargs):
    with _state_lock:
        STATE.update(kwargs)


def get_state():
    with _state_lock:
        return dict(STATE)


def check_connection():
    mode = settings.ANALYZER_MODE

    if mode != "real":
        _set(
            connected=True,
            port="DEMO",
            baud=settings.ANALYZER_BAUD,
            status="ready",
            message="Demo analyzer connected",
            last_error=None,
        )
        return True, "Demo analyzer connected"

    try:
        import serial
        from serial.tools import list_ports
    except ImportError:
        _set(connected=False, status="error", message="PySerial not installed", last_error="PySerial not installed")
        return False, "PySerial not installed"

    preferred = settings.ANALYZER_PORT
    detected = [p.device for p in list_ports.comports()]
    ports = [preferred] + [p for p in detected if p != preferred]

    last_error = None
    for port in ports:
        ser = None
        try:
            ser = serial.Serial(
                port=port,
                baudrate=settings.ANALYZER_BAUD,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
            )
            _set(
                connected=True,
                port=port,
                baud=settings.ANALYZER_BAUD,
                status="ready",
                message=f"Connected on {port}",
                last_error=None,
            )
            return True, f"Connected on {port}"
        except Exception as exc:
            last_error = str(exc)
        finally:
            try:
                if ser and ser.is_open:
                    ser.close()
            except Exception:
                pass

    _set(
        connected=False,
        status="error",
        message="Analyzer not connected",
        last_error=last_error or "No serial ports available",
    )
    return False, last_error or "No serial ports available"


def _demo_worker():
    _set(
        reading_active=True,
        status="waiting",
        message="Waiting for sample...",
        fat=None,
        snf=None,
        clr=None,
        last_error=None,
    )

    started = time.time()
    while not _stop_event.is_set():
        if time.time() - started >= 1.8:
            fat = round(random.uniform(3.4, 6.8), 2)
            snf = round(random.uniform(8.0, 9.4), 2)
            clr = calculate_clr(fat, snf)
            _set(
                connected=True,
                reading_active=False,
                status="success",
                message="Data received",
                fat=fat,
                snf=snf,
                clr=clr,
                port="DEMO",
                baud=settings.ANALYZER_BAUD,
                last_raw_text=f"FAT:{fat:.2f} SNF:{snf:.2f}",
                last_update_time=time.strftime("%Y-%m-%d %H:%M:%S"),
            )
            return
        time.sleep(0.05)


def _real_worker():
    import serial

    state = get_state()
    port = state.get("port") or settings.ANALYZER_PORT
    ser = None
    buffer = ""
    started = time.time()
    last_data_time = None

    _set(
        reading_active=True,
        status="waiting",
        message="Waiting for sample...",
        fat=None,
        snf=None,
        clr=None,
        last_error=None,
    )

    try:
        ser = serial.Serial(
            port=port,
            baudrate=settings.ANALYZER_BAUD,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.5,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )

        try:
            ser.reset_input_buffer()
            ser.reset_output_buffer()
        except Exception:
            pass

        while not _stop_event.is_set():
            if time.time() - started > settings.ANALYZER_TIMEOUT_SECONDS:
                _set(reading_active=False, status="timeout", message="No data received")
                return

            data = ser.read(256)

            if data:
                text = data.decode("ascii", errors="ignore")
                buffer += text
                buffer = buffer[-4000:]
                last_data_time = time.time()
                _set(last_raw_text=buffer)

                parsed = parse_text(buffer)
                if parsed:
                    fat, snf = parsed
                    clr = calculate_clr(fat, snf)
                    _set(
                        connected=True,
                        reading_active=False,
                        status="success",
                        message="Data received",
                        fat=round(fat, 2),
                        snf=round(snf, 2),
                        clr=clr,
                        last_update_time=time.strftime("%Y-%m-%d %H:%M:%S"),
                    )
                    return

            if buffer and last_data_time and time.time() - last_data_time > 2:
                parsed = parse_text(buffer)
                if parsed:
                    fat, snf = parsed
                    clr = calculate_clr(fat, snf)
                    _set(
                        connected=True,
                        reading_active=False,
                        status="success",
                        message="Data received",
                        fat=round(fat, 2),
                        snf=round(snf, 2),
                        clr=clr,
                        last_update_time=time.strftime("%Y-%m-%d %H:%M:%S"),
                    )
                    return

            time.sleep(0.05)

        _set(reading_active=False, status="ready", message="Stopped")

    except Exception as exc:
        _set(
            connected=False,
            reading_active=False,
            status="error",
            message="Reading failed",
            last_error=str(exc),
        )
    finally:
        try:
            if ser and ser.is_open:
                ser.close()
        except Exception:
            pass


def start_reading():
    global _worker

    with _worker_lock:
        if _worker and _worker.is_alive():
            return False, "Reading already in progress"

        ok, msg = check_connection()
        if not ok:
            return False, msg

        _stop_event.clear()
        target = _real_worker if settings.ANALYZER_MODE == "real" else _demo_worker
        _worker = threading.Thread(target=target, daemon=True)
        _worker.start()
        return True, "Reading started"


def stop_reading():
    _stop_event.set()
    _set(
        reading_active=False,
        status="ready" if get_state().get("connected") else "idle",
        message="Stopped",
        fat=None,
        snf=None,
        clr=None,
    )
    return True, "Stopped"
