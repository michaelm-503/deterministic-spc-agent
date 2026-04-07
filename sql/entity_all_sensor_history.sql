SELECT
    data.entity_group,
    data.entity,
    CAST(data.timestamp AS TIMESTAMP) AS ts,
    data.sensor,
    data.value,
    spc.ucl,
    spc.centerline,
    spc.lcl
FROM sensor_data AS data
LEFT JOIN sensor_spc_limits AS spc
    ON data.entity_group = spc.entity_group
   AND data.sensor = spc.sensor
WHERE data.entity_group = ?
  {{ENTITY_FILTER_CLAUSE}}
  AND data.operating_mode = 'normal'
  AND CAST(data.timestamp AS TIMESTAMP) >= COALESCE(?, TIMESTAMP '1900-01-01 00:00:00')
  AND CAST(data.timestamp AS TIMESTAMP) <  COALESCE(?, TIMESTAMP '9999-12-31 23:59:59')
ORDER BY ts, data.entity, data.sensor;