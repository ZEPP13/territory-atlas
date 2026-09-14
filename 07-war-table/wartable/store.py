"""Append-only JSONL stores for the ledger, signals and logbook.

Records are validated on the way in AND on the way out. A file that has been hand-edited into
an invalid state fails loudly with the file name and line number rather than being skipped.
"""
import json
import os
import uuid
from datetime import datetime, timezone

from . import DATA
from .schema import load as load_schema, validate

STORES = {
    "ledger":  ("ledger",  "registry_changes.jsonl", "ledger_change", "lc-"),
    "signals": ("signals", "signals.jsonl",          "signal",        "sig-"),
    "logbook": ("logbook", "logbook.jsonl",          "logbook_event", "lb-"),
}


class StoreError(Exception):
    pass


def now_iso():
    # millisecond precision: two taps in the same second must still have a defined order
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def new_id(prefix):
    return prefix + uuid.uuid4().hex[:12]


def path_for(store, data_dir=None):
    folder, fname, _, _ = STORES[store]
    return os.path.join(data_dir or DATA, folder, fname)


def read(store, data_dir=None):
    """Every record in a store, validated. Missing file = empty store."""
    p = path_for(store, data_dir)
    schema = load_schema(STORES[store][2])
    out, seen = [], set()
    if not os.path.exists(p):
        return out
    with open(p) as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                raise StoreError(f"{p}:{n}: not valid JSON ({e.msg})")
            errs = validate(rec, schema)
            if errs:
                raise StoreError(f"{p}:{n}: " + "; ".join(errs[:5]))
            if rec["id"] in seen:
                raise StoreError(f"{p}:{n}: duplicate id {rec['id']}")
            seen.add(rec["id"])
            out.append(rec)
    return out


def append(store, record, data_dir=None):
    """Validate and append one record. Returns the record as written."""
    errs = validate(record, load_schema(STORES[store][2]))
    if errs:
        raise StoreError("; ".join(errs[:5]))
    p = path_for(store, data_dir)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a") as fh:
        fh.write(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")
    return record


def validate_record(store, record):
    """Schema-check a record without writing it."""
    errs = validate(record, load_schema(STORES[store][2]))
    if errs:
        raise StoreError("; ".join(errs[:5]))
