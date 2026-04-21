SELECT
    DB_NAME()                                    AS [Database Name],
    s.name                                       AS [Schema Name],
    t.name                                       AS [Table Name],
    c.column_id                                  AS [Column Order],
    c.name                                       AS [Column Name],
    tp.name                                      AS [Data Type],
    CASE WHEN tp.name IN ('varchar','nvarchar','char','nchar') 
         THEN CAST(c.max_length AS VARCHAR) 
         ELSE NULL END                           AS [Max Length],
    CASE WHEN c.is_nullable = 1 
         THEN 'YES' ELSE 'NO' END               AS [Nullable],

    -- Primary Key
    CASE WHEN pk.column_id IS NOT NULL 
         THEN 'YES' ELSE 'NO' END               AS [Is Primary Key],

    -- Foreign Key
    CASE WHEN fk.parent_column_id IS NOT NULL 
         THEN 'YES' ELSE 'NO' END               AS [Is Foreign Key],
    fk_ref.name                                  AS [FK References Table],
    fk_ref_col.name                              AS [FK References Column],

    -- Unique Key
    CASE WHEN uq.column_id IS NOT NULL 
         THEN 'YES' ELSE 'NO' END               AS [Is Unique Key],

    -- Index (non-PK, non-unique)
    CASE WHEN ix.column_id IS NOT NULL 
         THEN 'YES' ELSE 'NO' END               AS [Has Index],
    ix_name.name                                 AS [Index Name]

FROM sys.tables t
JOIN sys.schemas s 
    ON t.schema_id = s.schema_id
JOIN sys.columns c 
    ON c.object_id = t.object_id
JOIN sys.types tp 
    ON c.user_type_id = tp.user_type_id

-- Primary Key lookup
LEFT JOIN (
    SELECT ic.object_id, ic.column_id
    FROM sys.index_columns ic
    JOIN sys.indexes i ON i.object_id = ic.object_id 
        AND i.index_id = ic.index_id
    WHERE i.is_primary_key = 1
) pk ON pk.object_id = t.object_id AND pk.column_id = c.column_id

-- Foreign Key lookup
LEFT JOIN (
    SELECT fkc.parent_object_id, fkc.parent_column_id,
           fkc.referenced_object_id, fkc.referenced_column_id
    FROM sys.foreign_key_columns fkc
) fk ON fk.parent_object_id = t.object_id AND fk.parent_column_id = c.column_id

LEFT JOIN sys.tables fk_ref 
    ON fk_ref.object_id = fk.referenced_object_id
LEFT JOIN sys.columns fk_ref_col 
    ON fk_ref_col.object_id = fk.referenced_object_id 
    AND fk_ref_col.column_id = fk.referenced_column_id

-- Unique Key lookup (unique index, not PK)
LEFT JOIN (
    SELECT ic.object_id, ic.column_id
    FROM sys.index_columns ic
    JOIN sys.indexes i ON i.object_id = ic.object_id 
        AND i.index_id = ic.index_id
    WHERE i.is_unique = 1 AND i.is_primary_key = 0
) uq ON uq.object_id = t.object_id AND uq.column_id = c.column_id

-- Index lookup (any index, not PK or unique)
LEFT JOIN (
    SELECT ic.object_id, ic.column_id, ic.index_id
    FROM sys.index_columns ic
    JOIN sys.indexes i ON i.object_id = ic.object_id 
        AND i.index_id = ic.index_id
    WHERE i.is_primary_key = 0 AND i.is_unique = 0
) ix ON ix.object_id = t.object_id AND ix.column_id = c.column_id

LEFT JOIN sys.indexes ix_name 
    ON ix_name.object_id = t.object_id 
    AND ix_name.index_id = ix.index_id

WHERE s.name = 'dbo'
ORDER BY t.name, c.column_id;