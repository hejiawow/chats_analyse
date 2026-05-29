-- 删除 case_extraction_results 表中的 11 个旧字段
-- 运行方式：psql -U <user> -d <db> -f app/scripts/drop_old_columns.sql

ALTER TABLE case_extraction_results DROP COLUMN IF EXISTS scenario_type;
ALTER TABLE case_extraction_results DROP COLUMN IF EXISTS customer_type;
ALTER TABLE case_extraction_results DROP COLUMN IF EXISTS communication_stage;
ALTER TABLE case_extraction_results DROP COLUMN IF EXISTS sales_quote;
ALTER TABLE case_extraction_results DROP COLUMN IF EXISTS sales_ability_score;
ALTER TABLE case_extraction_results DROP COLUMN IF EXISTS sales_ability_desc;
ALTER TABLE case_extraction_results DROP COLUMN IF EXISTS replicability_score;
ALTER TABLE case_extraction_results DROP COLUMN IF EXISTS replicability_desc;
ALTER TABLE case_extraction_results DROP COLUMN IF EXISTS detail_score;
ALTER TABLE case_extraction_results DROP COLUMN IF EXISTS detail_desc;
ALTER TABLE case_extraction_results DROP COLUMN IF EXISTS comprehensive_review;
