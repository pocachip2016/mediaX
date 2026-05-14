#!/usr/bin/env python3
"""Verify detail.csv — check required fields and data quality."""

import csv
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "watcha"
detail_file = DATA_DIR / "detail.csv"

with open(detail_file) as f:
    reader = csv.DictReader(f)
    rows = list(reader)

required_fields = ["title", "year", "poster_url"]
valid_count = 0

for row in rows:
    if all(row.get(field) for field in required_fields):
        valid_count += 1

success_rate = valid_count / len(rows) if rows else 0
print(f"Detail.csv validation: {valid_count}/{len(rows)} rows with required fields ({success_rate*100:.1f}%)")

if success_rate >= 0.9:
    print("✓ Validation OK (≥90%)")
    exit(0)
else:
    print("✗ Validation FAILED (<90%)")
    exit(1)
