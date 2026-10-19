# Domain knowledge — solar plant MIPAZ01_01 (MySQL)

This text goes into the model prompt, so it is written in English. Persian terms
are quoted because they are what the user actually types.

## What each table holds

- `inverter_data` — "اینورتر". One inverter, sampled every ~25 seconds.
- `lvpanel_data` — "پنل فشار ضعیف", the low-voltage panel. Only this table
  has `plant_id` and `zone_id`.
- `mvpanel_data` — "پنل فشار متوسط", the medium-voltage panel. Per-phase columns
  (`voltage_a`, `active_pow_a`, …) do not exist here; only the totals do.
- `string_data` — "استرینگ", the PV strings. Only `voltage`, `current`, `power`.

Every table has `timestamp`, `ingested_at` and `device_code`.

## Persian words to columns

| The user says | They mean |
|---|---|
| «مصرف»، «استفاده» | active power — `tot_active_pow` (NOT the energy counters) |
| «تولید»، «تولیدی»، «بازده» | energy counters — `daily_pow_yield`, `monthly_pow_yield`, `tot_pow_yield` |
| «دما»، «حرارت» | `int_temp` |
| «خطا»، «خرابی»، «مشکل»، «آلارم» | `fa_al_code` — read the trap below first |
| «ولتاژ»، «ولتاژ متوسط» | `voltage_avg` — the phase voltage (~227 V), NOT `voltage_ll_avg` |
| «ولتاژ خط به خط»، «ولتاژ خطی» | `voltage_ll_avg` (~393 V), only when the user says so |
| «جریان» | `current_*` |
| «توان» | the `*_pow` columns (instantaneous) |
| «انرژی» | the `*_eng_*` / `*_yield` columns (cumulative) |
| «امروز»، «روز آخر»، «آخرین» | order by `timestamp` |
| «الان»، «در حال حاضر» | the single newest row: `ORDER BY timestamp DESC LIMIT 1` |

If the question is about something outside these tables — irradiance, wind
speed, humidity, electricity price, any forecast of the future — do not invent a
column. Answer per security rule 5.

## Data traps — read before writing a query

**`tot_reactive_pow` in `inverter_data` is an unsigned 32-bit number holding
signed values.** 5,927 of 10,161 rows store a negative reactive power as
`value + 2^32`. A plain `AVG` returns about 2.5 billion, which is nonsense; the
true average is about -27. Whenever this column is aggregated, convert it first:

```sql
CASE WHEN tot_reactive_pow >= 2147483648
     THEN tot_reactive_pow - 4294967296
     ELSE tot_reactive_pow END
```

Only this one column is affected. The panels store negative reactive power
correctly as ordinary negative numbers, so never apply this conversion there.

**`fa_al_code` is `0` in every single row.** No fault was ever recorded in this
data. A correct "list the errors" query returns nothing — that is the true
answer, not a bug. Say so plainly rather than loosening the filter until
something appears. It is an integer: compare with `0`, never with `'0'`.

**`fa_al_message` does not exist.** The column was empty in every row and was
dropped on import. Never reference it.

**Energy columns are counters, not measurements.** `daily_pow_yield` starts at
zero each morning and climbs. "How much was produced today" is the counter's
value in the newest row (`ORDER BY timestamp DESC LIMIT 1`), never a `SUM` —
summing a counter adds every intermediate reading and inflates the answer enormously.

**`mccb` and `status` are strings, not booleans.** `mccb` is `'ON'` or
`'no_conn'`; `status` is `'ON'` or `'OFF'` on the inverter and `'ON'` or
`'no_conn'` on the low-voltage panel.

**`work_state` has four values:** `'Run'`, `'Standby'`, `'Initial standby'`,
`'Starting'`. The last two are rare but real.

**`timestamp` and `ts` both exist** and are Unix epoch seconds within five
seconds of each other. Always use `timestamp`.

**`plant_id` and `zone_id` are both `1` everywhere** in this data. Grouping by
them returns a single group and tells the user nothing.

## SQL limits of this assistant

One `SELECT` on one table per question: no `JOIN`, `UNION`, subquery or `WITH`.
So a question that seems to need two steps (for example "the maximum on the last
day") must be answered by the closest single-table query, as the examples show.

## Time meaning and readable answers

`timestamp` is the canonical measurement time: Unix epoch **seconds in UTC**,
not milliseconds. `ts` is a secondary clock, not a preformatted date. Do not
switch to `ingested_at` to answer when a measurement happened: ingestion time
is not interchangeable with measurement time.

When returning the latest reading, a date/hour, or the start/end of a time
range, include a readable date-time column in the query result itself. The
summary model does not receive this documentation. Do not rely on it to guess
a calendar date from a raw epoch number. Keep filtering and sorting on numeric
`timestamp`; formatting is a read-only projection and must not change stored data.
For a range, format both endpoints, not just the first, and preserve the actual
range requested by the user.

Use the timezone explicitly requested by the user and label it in the result.
If none is specified, use and label UTC; do not silently assume the database
server's timezone. For Iran time, use `Asia/Tehran` with a real timezone-aware
conversion; never add a fixed offset for all historical dates. Persian prose
does not imply a Jalali calendar: use a Gregorian `YYYY-MM-DD HH:mm:ss` value
unless a verified Jalali conversion is available or requested. Never relabel a
Gregorian date as Solar Hijri. If the requested conversion cannot be performed
with the allowed query functions, state the limitation instead of inventing it.

Verified conversion example (illustration only, NOT a current customer result):
`1780918908` is `2026-06-08 11:41:48 UTC`, or
`2026-06-08 15:11:48 Asia/Tehran`. Never reuse this example's date as an answer
without the actual query result. Prefer a Persian sentence with the readable
time and its timezone rather than «آخرین زمان ثبت‌شده ۱۷۸۰۹۱۸۹۰۸».

MySQL/MariaDB: `FROM_UNIXTIME` uses the session timezone, which must not be
assumed to be UTC or Iran. For a deterministic UTC projection, add epoch seconds
to a timezone-free UTC epoch origin using allowed read-only functions:

```sql
SELECT DATE_FORMAT(
  DATE_ADD(CAST('1970-01-01 00:00:00' AS DATETIME), INTERVAL `timestamp` SECOND),
  '%Y-%m-%d %H:%i:%s UTC') AS measurement_time_utc
FROM inverter_data ORDER BY `timestamp` DESC LIMIT 1
```

Include the other requested columns as needed. This example guarantees a UTC
label, not a Tehran or Jalali conversion. Do not use a disallowed timezone
function or change the database session to bypass the guard.
