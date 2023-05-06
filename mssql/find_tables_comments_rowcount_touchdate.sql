-- Following query is for providing the comment, row counts and last time updated
SELECT t.table_catalog,
       t.table_schema,
       t.table_name,
       t.table_type,
       c.value                                                          AS
       TABLE_COMMENT,
       p.row_count,
       COALESCE(u.last_user_seek, u.last_user_scan, u.last_user_update) AS
       last_touch_date
FROM   information_schema.tables t
       LEFT JOIN sys.extended_properties c
              ON c.major_id = Object_id(t.table_schema + '.' + t.table_name)
                 AND c.minor_id = 0
                 AND c.NAME = 'MS_Description'
       LEFT JOIN (SELECT object_id,
                         Sum(row_count) AS row_count
                  FROM   sys.dm_db_partition_stats
                  WHERE  index_id < 2
                  GROUP  BY object_id) p
              ON p.object_id = Object_id(t.table_schema + '.' + t.table_name)
       LEFT JOIN sys.dm_db_index_usage_stats u
              ON u.object_id = Object_id(t.table_schema + '.' + t.table_name)
                 AND u.database_id = Db_id()
                 AND u.index_id < 2
WHERE  t.table_type = 'BASE TABLE'
       AND t.table_schema = 'dbo'
ORDER  BY t.table_name; 