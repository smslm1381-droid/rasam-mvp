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
