"""Google Calendar & Tasks API service layer.

Provides high-level functions to fetch/create events and tasks,
with automatic fallback to the local SQLite cache on network errors.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.auth import get_credentials
from src import cache

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Service helpers (cached singletons — avoids repeated discovery overhead)
# ---------------------------------------------------------------------------

_cached_calendar_service = None
_cached_tasks_service = None


def _calendar_service():
    global _cached_calendar_service
    if _cached_calendar_service is None:
        _cached_calendar_service = build("calendar", "v3", credentials=get_credentials())
    return _cached_calendar_service


def _tasks_service():
    global _cached_tasks_service
    if _cached_tasks_service is None:
        _cached_tasks_service = build("tasks", "v1", credentials=get_credentials())
    return _cached_tasks_service


def invalidate_services():
    """Clear cached service objects (e.g. after token refresh)."""
    global _cached_calendar_service, _cached_tasks_service
    _cached_calendar_service = None
    _cached_tasks_service = None


# ---------------------------------------------------------------------------
# Read — Fetch
# ---------------------------------------------------------------------------

def fetch_month_events(year: int, month: int) -> list[dict[str, Any]]:
    """Fetch calendar events for the given month from the Google Calendar API.

    Falls back to local cache on any network / API error.
    """
    time_min = datetime(year, month, 1).isoformat() + "Z"
    if month == 12:
        time_max = datetime(year + 1, 1, 1).isoformat() + "Z"
    else:
        time_max = datetime(year, month + 1, 1).isoformat() + "Z"

    try:
        service = _calendar_service()
        result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                maxResults=500,
            )
            .execute()
        )
        items = result.get("items", [])
        events = _normalize_calendar_events(items)
        cache.clear_month(year, month)
        cache.save_events(events)
        return events
    except HttpError as e:
        if e.resp.status in (401, 403):
            invalidate_services()
        log.warning("Calendar API failed — loading from cache", exc_info=True)
        return cache.load_events(year, month)
    except Exception:
        log.warning("Calendar API failed — loading from cache", exc_info=True)
        return cache.load_events(year, month)


def fetch_month_tasks(year: int, month: int) -> list[dict[str, Any]]:
    """Fetch tasks whose due date falls within the given month.

    Falls back to local cache on any network / API error.
    """
    due_min = datetime(year, month, 1).isoformat() + "Z"
    if month == 12:
        due_max = datetime(year + 1, 1, 1).isoformat() + "Z"
    else:
        due_max = datetime(year, month + 1, 1).isoformat() + "Z"

    try:
        service = _tasks_service()
        tasklists = service.tasklists().list(maxResults=50).execute().get("items", [])

        all_tasks: list[dict[str, Any]] = []
        for tl in tasklists:
            tasks_result = (
                service.tasks()
                .list(
                    tasklist=tl["id"],
                    dueMin=due_min,
                    dueMax=due_max,
                    showCompleted=True,
                    maxResults=200,
                )
                .execute()
            )
            all_tasks.extend(tasks_result.get("items", []))

        normalized = _normalize_tasks(all_tasks)
        cache.save_events(normalized)
        return normalized
    except HttpError as e:
        if e.resp.status in (401, 403):
            invalidate_services()
        log.warning("Tasks API failed — loading from cache", exc_info=True)
        return [e for e in cache.load_events(year, month) if e["source"] == "tasks"]
    except Exception:
        log.warning("Tasks API failed — loading from cache", exc_info=True)
        return [e for e in cache.load_events(year, month) if e["source"] == "tasks"]


def fetch_all(year: int, month: int) -> list[dict[str, Any]]:
    """Return combined calendar events + tasks for the month (parallel)."""
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_events = pool.submit(fetch_month_events, year, month)
        fut_tasks = pool.submit(fetch_month_tasks, year, month)
        for fut in as_completed([fut_events, fut_tasks]):
            try:
                results.extend(fut.result())
            except Exception:
                log.warning("Parallel fetch error", exc_info=True)
    return results


# ---------------------------------------------------------------------------
# Write — Create
# ---------------------------------------------------------------------------

def create_event(summary: str, date: str, start_time: str | None = None) -> dict:
    """Create a Google Calendar event.

    Args:
        summary: Event title.
        date: ISO date string, e.g. "2026-03-15".
        start_time: Optional HH:MM (24h). If omitted an all-day event is created.
    """
    service = _calendar_service()
    if start_time:
        start_dt = datetime.fromisoformat(f"{date}T{start_time}:00")
        end_dt = start_dt + timedelta(hours=1)
        body = {
            "summary": summary,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Seoul"},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": "Asia/Seoul"},
        }
    else:
        # Google all-day end date is exclusive, so +1 day
        end_date = (datetime.fromisoformat(date) + timedelta(days=1)).strftime("%Y-%m-%d")
        body = {
            "summary": summary,
            "start": {"date": date},
            "end": {"date": end_date},
        }
    return service.events().insert(calendarId="primary", body=body).execute()


def delete_event(event_id: str) -> None:
    """Delete a Google Calendar event by ID."""
    service = _calendar_service()
    service.events().delete(calendarId="primary", eventId=event_id).execute()


def update_event(
    event_id: str, summary: str, date: str, start_time: str | None = None
) -> dict:
    """Update an existing Google Calendar event.

    Args:
        event_id: The event ID to update.
        summary: New event title.
        date: ISO date string, e.g. "2026-03-15".
        start_time: Optional HH:MM (24h). If omitted the event becomes all-day.
    """
    service = _calendar_service()
    if start_time:
        start_dt = datetime.fromisoformat(f"{date}T{start_time}:00")
        end_dt = start_dt + timedelta(hours=1)
        body = {
            "summary": summary,
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": "Asia/Seoul",
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": "Asia/Seoul",
            },
        }
    else:
        end_date = (datetime.fromisoformat(date) + timedelta(days=1)).strftime("%Y-%m-%d")
        body = {
            "summary": summary,
            "start": {"date": date},
            "end": {"date": end_date},
        }
    return (
        service.events()
        .update(calendarId="primary", eventId=event_id, body=body)
        .execute()
    )


def delete_task(task_id: str) -> None:
    """Delete a Google Task by ID."""
    service = _tasks_service()
    tasklists = service.tasklists().list(maxResults=50).execute().get("items", [])
    for tl in tasklists:
        try:
            service.tasks().delete(tasklist=tl["id"], task=task_id).execute()
            return
        except HttpError:
            continue
    raise RuntimeError(f"Task {task_id} not found in any task list.")


def update_task(task_id: str, title: str, date: str) -> dict:
    """Update an existing Google Task.

    Args:
        task_id: The task ID to update.
        title: New task title.
        date: ISO date string, e.g. "2026-03-15".
    """
    service = _tasks_service()
    tasklists = service.tasklists().list(maxResults=50).execute().get("items", [])
    for tl in tasklists:
        try:
            task = service.tasks().get(tasklist=tl["id"], task=task_id).execute()
            task["title"] = title
            task["due"] = f"{date}T00:00:00.000Z"
            return (
                service.tasks()
                .update(tasklist=tl["id"], task=task_id, body=task)
                .execute()
            )
        except HttpError:
            continue
    raise RuntimeError(f"Task {task_id} not found in any task list.")


def create_task(title: str, date: str) -> dict:
    """Create a Google Task on the default task list.

    Args:
        title: Task title.
        date: ISO date string, e.g. "2026-03-15".
    """
    service = _tasks_service()
    tasklists = service.tasklists().list(maxResults=1).execute().get("items", [])
    if not tasklists:
        raise RuntimeError("No task list found in Google Tasks.")
    tasklist_id = tasklists[0]["id"]
    body = {
        "title": title,
        "due": f"{date}T00:00:00.000Z",
    }
    return service.tasks().insert(tasklist=tasklist_id, body=body).execute()


# ---------------------------------------------------------------------------
# Normalizers
# ---------------------------------------------------------------------------

def _normalize_calendar_events(items: list[dict]) -> list[dict[str, Any]]:
    """Convert raw Google Calendar API items into a flat internal format.

    Multi-day or overnight events are duplicated onto each date they span.
    """
    results = []
    for item in items:
        start = item.get("start", {})
        end = item.get("end", {})
        summary_text = item.get("summary", "(제목 없음)")
        event_id = item["id"]

        if "dateTime" in start:
            # Timed event — may span multiple days
            start_dt = datetime.fromisoformat(start["dateTime"])
            end_dt = datetime.fromisoformat(end.get("dateTime", start["dateTime"]))
            time_prefix = f"[{start_dt.strftime('%H:%M')}] "

            start_date = start_dt.date()
            end_date = end_dt.date()
            # If event ends exactly at midnight, it doesn't occupy that day
            if end_dt.hour == 0 and end_dt.minute == 0 and end_dt.second == 0:
                end_date -= timedelta(days=1)

            current = start_date
            while current <= end_date:
                prefix = time_prefix if current == start_date else "[연속] "
                results.append(
                    {
                        "id": event_id,
                        "date": current.isoformat(),
                        "summary": f"{prefix}{summary_text}",
                        "source": "calendar",
                    }
                )
                current += timedelta(days=1)
        else:
            # All-day event — may span multiple days
            start_date = datetime.fromisoformat(start.get("date", "")).date()
            end_date = datetime.fromisoformat(end.get("date", start.get("date", ""))).date()
            # Google all-day end date is exclusive
            end_date -= timedelta(days=1)

            current = start_date
            while current <= end_date:
                results.append(
                    {
                        "id": event_id,
                        "date": current.isoformat(),
                        "summary": summary_text,
                        "source": "calendar",
                    }
                )
                current += timedelta(days=1)

    return results


def _normalize_tasks(items: list[dict]) -> list[dict[str, Any]]:
    """Convert raw Google Tasks API items into a flat internal format."""
    results = []
    for item in items:
        due = item.get("due", "")
        date_only = due[:10] if due else ""
        if not date_only:
            continue

        status = item.get("status", "")
        check = "[x]" if status == "completed" else "[ ]"

        results.append(
            {
                "id": item["id"],
                "date": date_only,
                "summary": f"{check} {item.get('title', '(제목 없음)')}",
                "source": "tasks",
            }
        )
    return results
