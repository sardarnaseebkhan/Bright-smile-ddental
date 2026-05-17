"""
Mock calendar service — no Google credentials required.
Generates realistic available slots and saves bookings to appointments.json.
"""
import json
import os
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

import dateparser

from utils.logging import get_logger

logger = get_logger(__name__)

CLINIC_TZ = ZoneInfo("America/New_York")
APPOINTMENTS_FILE = os.path.join(os.path.dirname(__file__), "..", "appointments.json")

WEEKDAY_HOURS = (time(8, 0), time(18, 0))
SATURDAY_HOURS = (time(9, 0), time(14, 0))


def _parse_date(preferred_date: str) -> datetime:
    parsed = dateparser.parse(
        preferred_date,
        settings={
            "PREFER_DATES_FROM": "future",
            "TIMEZONE": "America/New_York",
            "RETURN_AS_TIMEZONE_AWARE": True,
        },
    )
    return parsed if parsed else datetime.now(CLINIC_TZ) + timedelta(days=1)


def _load_booked() -> list:
    if not os.path.exists(APPOINTMENTS_FILE):
        return []
    with open(APPOINTMENTS_FILE, "r") as f:
        return json.load(f)


def _save_booking(record: dict):
    booked = _load_booked()
    booked.append(record)
    with open(APPOINTMENTS_FILE, "w") as f:
        json.dump(booked, f, indent=2)


def _is_taken(slot: datetime, duration_minutes: int, booked: list) -> bool:
    slot_end = slot + timedelta(minutes=duration_minutes)
    for appt in booked:
        try:
            start = datetime.fromisoformat(appt["appointment_datetime"])
            if start.tzinfo is None:
                start = start.replace(tzinfo=CLINIC_TZ)
            end = start + timedelta(minutes=appt.get("duration_minutes", 60))
            if slot < end and slot_end > start:
                return True
        except Exception:
            continue
    return False


def _clinic_slots(day: datetime.date, duration_minutes: int, time_pref: str) -> list:
    weekday = day.weekday()
    if weekday == 6:
        return []
    open_t, close_t = SATURDAY_HOURS if weekday == 5 else WEEKDAY_HOURS
    slots = []
    current = datetime.combine(day, open_t, tzinfo=CLINIC_TZ)
    end_of_day = datetime.combine(day, close_t, tzinfo=CLINIC_TZ)
    step = timedelta(minutes=60)
    while current + timedelta(minutes=duration_minutes) <= end_of_day:
        hour = current.hour
        if time_pref == "morning" and hour >= 12:
            break
        if time_pref == "afternoon" and not (12 <= hour < 17):
            current += step
            continue
        if time_pref == "evening" and hour < 17:
            current += step
            continue
        slots.append(current)
        current += step
    return slots


async def check_available_slots(
    preferred_date: str,
    appointment_type: str,
    preferred_time_of_day: str = "any",
    duration_minutes: int = 60,
) -> dict:
    target_dt = _parse_date(preferred_date)
    target_date = target_dt.date()
    booked = _load_booked()

    search_dates = []
    d = target_date
    while len(search_dates) < 3:
        if d.weekday() < 6:
            search_dates.append(d)
        d += timedelta(days=1)

    available = []
    for day in search_dates:
        for slot in _clinic_slots(day, duration_minutes, preferred_time_of_day):
            if not _is_taken(slot, duration_minutes, booked):
                available.append(slot)

    available_iso = [s.isoformat() for s in available[:6]]
    logger.info(f"Available slots for '{preferred_date}': {available_iso}")
    return {
        "available_slots": available_iso,
        "appointment_type": appointment_type,
        "searched_dates": [str(d) for d in search_dates],
    }


async def book_appointment(
    patient_name: str,
    patient_phone: str,
    appointment_datetime: str,
    appointment_type: str,
    duration_minutes: int = 60,
    is_new_patient: bool = False,
    notes: str = "",
) -> dict:
    start_dt = datetime.fromisoformat(appointment_datetime)
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=CLINIC_TZ)

    record = {
        "patient_name": patient_name,
        "patient_phone": patient_phone,
        "appointment_datetime": start_dt.isoformat(),
        "duration_minutes": duration_minutes,
        "appointment_type": appointment_type,
        "is_new_patient": is_new_patient,
        "notes": notes,
        "booked_at": datetime.now(CLINIC_TZ).isoformat(),
    }
    _save_booking(record)

    event_id = f"local_{int(datetime.now().timestamp())}"
    logger.info(f"Appointment saved locally: {event_id} for {patient_name}")
    return {
        "success": True,
        "event_id": event_id,
        "event_link": "",
        "confirmed_datetime": appointment_datetime,
        "patient_name": patient_name,
    }
