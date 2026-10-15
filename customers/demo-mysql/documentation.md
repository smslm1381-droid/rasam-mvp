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
