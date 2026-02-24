SELECT
    entity,
    data.entity_group,
    CAST(timestamp AS TIMESTAMP) AS ts,
    operating_mode,
    hours_since_maintenance,
    failure_type,
    data.sensor,
    value,
    spc.ucl,
    spc.centerline,
    spc.lcl
FROM sensor_data AS data
LEFT JOIN sensor_spc_limits AS spc
ON data.entity_group = spc.entity_group
    AND data.sensor = spc.sensor
WHERE data.entity_group = ?
    AND data.sensor = ?
    AND operating_mode = 'normal'
ORDER BY ts;