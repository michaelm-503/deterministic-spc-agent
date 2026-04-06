WITH entity_timestamps AS (
    SELECT DISTINCT
        data.entity_group,
        data.entity,
        CAST(data.timestamp AS TIMESTAMP) AS ts,
        data.hours_since_maintenance,
        data.failure_type
    FROM sensor_data AS data
    WHERE data.entity_group = ?
      {{ENTITY_FILTER_CLAUSE}}
      AND CAST(data.timestamp AS TIMESTAMP) >= COALESCE(?, TIMESTAMP '1900-01-01 00:00:00')
      AND CAST(data.timestamp AS TIMESTAMP) <  COALESCE(?, TIMESTAMP '9999-12-31 23:59:59')
      AND data.operating_mode = 'normal'
),
pm_event_ticks AS (
    SELECT
        entity_group,
        entity,
        ts,
        hours_since_maintenance AS hours_pre_pm,
        failure_type,
        LEAD(hours_since_maintenance) OVER (
            PARTITION BY entity
            ORDER BY ts
        ) AS next_hours_since_maintenance
    FROM entity_timestamps
),
pm_events AS (
    SELECT
        entity_group,
        entity,
        ts,
        hours_pre_pm,
        failure_type
    FROM pm_event_ticks
    WHERE hours_pre_pm > next_hours_since_maintenance
)
SELECT
    evt.entity_group,
    evt.entity,
    evt.ts,
    evt.hours_pre_pm,
    evt.failure_type,
    data.operating_mode,
    data.sensor,
    data.value,
    spc.ucl,
    spc.centerline,
    spc.lcl
FROM pm_events AS evt
JOIN sensor_data AS data
    ON data.entity_group = evt.entity_group
   AND data.entity = evt.entity
   AND CAST(data.timestamp AS TIMESTAMP) = evt.ts
   AND data.operating_mode = 'normal'
LEFT JOIN sensor_spc_limits AS spc
    ON data.entity_group = spc.entity_group
   AND data.sensor = spc.sensor
ORDER BY evt.ts, evt.entity, data.sensor;
