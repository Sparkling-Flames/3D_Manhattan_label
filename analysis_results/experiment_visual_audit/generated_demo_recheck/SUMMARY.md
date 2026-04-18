# Experiment Visual Audit

## Core counts
- tier definition: T = all rows; I = in-scope rows; M = in-scope and type3_flag = False
- tier T: 5 rows, 5 tasks
- tier I: 5 rows, 5 tasks
- tier M: 5 rows, 5 tasks

## Field audit
- mixed scope tasks: 0
- type3 rows: 0
- layout gate fail rows: 0
- type4 rows: 5
- active_time missing rows: 0

## Schema alignment
- missing formal fields: 2
- compatibility fallback fields: 6

## Scope conflicts
- conflict tasks: 0

## Active-time row audit
- short_time_rows: 5 (rate=1.0000)
- long_time_rows: 0 (rate=0.0000)
- unknown_id_rows: 0 (rate=0.0000)
- multi_session_rows: 0 (rate=0.0000)
- missing_script_version_rows: 5 (rate=1.0000)
- active_time_missing_rows: 0 (rate=0.0000)
