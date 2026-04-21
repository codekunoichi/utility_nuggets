SELECT 
    t.name                              AS [Table Name],
    s.name                              AS [Schema],
    t.create_date                       AS [Table Created],
    t.modify_date                       AS [Schema Last Modified],
    p.rows                              AS [Total Rows],
    MAX(ius.last_user_update)           AS [Last Write Since Restart],
    MAX(ius.last_user_seek)             AS [Last Read Since Restart],
    COUNT(DISTINCT c.column_id)         AS [Column Count],
    STRING_AGG(
        CASE WHEN ic.object_id IS NOT NULL 
             THEN c.name END, ', ')     AS [Primary Key Columns]
FROM sys.tables t
JOIN sys.schemas s 
    ON t.schema_id = s.schema_id
JOIN sys.partitions p 
    ON t.object_id = p.object_id AND p.index_id IN (0, 1)
JOIN sys.columns c 
    ON c.object_id = t.object_id
LEFT JOIN sys.dm_db_index_usage_stats ius 
    ON ius.object_id = t.object_id AND ius.database_id = DB_ID()
LEFT JOIN sys.indexes i 
    ON i.object_id = t.object_id AND i.is_primary_key = 1
LEFT JOIN sys.index_columns ic 
    ON ic.object_id = i.object_id AND ic.index_id = i.index_id 
    AND ic.column_id = c.column_id
WHERE s.name = 'dbo'
GROUP BY t.name, s.name, t.create_date, t.modify_date, p.rows
ORDER BY p.rows DESC;