# Domain knowledge — solar plant MIPAZ01_01

This text goes into the model prompt, so it is written in English. Persian terms
are quoted because they are what the user actually types.

## What each collection holds

- `inverter_data` — "اینورتر". One inverter, sampled every ~25 seconds.
- `lvpanel_data` — "پنل فشار ضعیف", the low-voltage panel. Only this collection
  has `plant_id` and `zone_id`.
- `mvpanel_data` — "پنل فشار متوسط", the medium-voltage panel. Per-phase fields
  (`voltage_a`, `active_pow_a`, …) do not exist here; only the totals do.
- `string_data` — "استرینگ", the PV strings. Only `voltage`, `current`, `power`.

Every collection has `timestamp`, `ingested_at` and `device_code`.

## Persian words to fields

| The user says | They mean |
|---|---|
| «مصرف»، «استفاده» | active power — `tot_active_pow` (NOT the energy counters) |
| «تولید»، «تولیدی»، «بازده» | energy counters — `daily_pow_yield`, `monthly_pow_yield`, `tot_pow_yield` |
| «دما»، «حرارت» | `int_temp` |
| «خطا»، «خرابی»، «مشکل»، «آلارم» | `fa_al_code` — read the trap below first |
| «ولتاژ»، «ولتاژ متوسط» | `voltage_avg` — the phase voltage (~227 V), NOT `voltage_ll_avg` |
| «ولتاژ خط به خط»، «ولتاژ خطی» | `voltage_ll_avg` (~393 V), only when the user says so |
| «جریان» | `current_*` |
| «توان» | the `*_pow` fields (instantaneous) |
| «انرژی» | the `*_eng_*` / `*_yield` fields (cumulative) |
| «امروز»، «روز آخر»، «آخرین» | filter on `timestamp` |
| «الان»، «در حال حاضر» | the single newest document: `$sort` desc on `timestamp`, `$limit` 1 |

If the question is about something outside these collections — irradiance, wind
speed, humidity, electricity price, any forecast of the future — do not invent a
field. Answer per security rule 5.

## Data traps — read before writing a query

**`tot_reactive_pow` in `inverter_data` is an unsigned 32-bit number holding
signed values.** 5,927 of 10,161 documents store a negative reactive power as
`value + 2^32`. A plain `$avg` returns about 2.5 billion, which is nonsense; the
true average is about -27. Whenever this field is aggregated, convert it first:

```json
{"$cond": [{"$gte": ["$tot_reactive_pow", 2147483648]},
           {"$subtract": ["$tot_reactive_pow", 4294967296]},
           "$tot_reactive_pow"]}
```

Only this one field is affected. The panels store negative reactive power
correctly as ordinary negative numbers, so never apply this conversion there.

**`fa_al_code` is `0` in every single document.** No fault was ever recorded in
this data. A correct "list the errors" query returns nothing — that is the true
answer, not a bug. Say so plainly rather than loosening the filter until
something appears. It is an integer: compare with `0`, never with `"0"`.

**`fa_al_message` does not exist.** The field was empty in every row and was
dropped on import. Never reference it.

**Energy fields are counters, not measurements.** `daily_pow_yield` starts at
zero each morning and climbs. "How much was produced today" is the `$max` of the
counter for the latest day, never a `$sum` — summing a counter adds every
intermediate reading and inflates the answer enormously.

**`mccb` and `status` are strings, not booleans.** `mccb` is `"ON"` or
`"no_conn"`; `status` is `"ON"` or `"OFF"` on the inverter and `"ON"` or
`"no_conn"` on the low-voltage panel.

**`work_state` has four values:** `"Run"`, `"Standby"`, `"Initial standby"`,
`"Starting"`. The last two are rare but real.

**`timestamp` and `ts` both exist** and are Unix epoch seconds within five
seconds of each other. Always use `timestamp`.

**`plant_id` and `zone_id` are both `1` everywhere** in this data. Grouping by
them returns a single group and tells the user nothing.

<!-- rasam:required -->
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

MongoDB: convert seconds to milliseconds before `$toDate`, then use
`$dateToString` with an explicit `timezone`. Example read-only projection:

```json
{"$project": {"_id": 0, "measurement_time_utc": {"$dateToString": {
  "date": {"$toDate": {"$multiply": ["$timestamp", 1000]}},
  "format": "%Y-%m-%d %H:%M:%S UTC", "timezone": "UTC"}}}}
```

Include the other fields needed by the question in the same projection; this
example shows only time formatting. Use the same conversion on each range endpoint.
<!-- /rasam:required -->
