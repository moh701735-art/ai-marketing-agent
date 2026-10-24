-- 00_harness.sql : أدوات اختبار بسيطة (لا تعتمد pgTAP). كل اختبار يكتب صفاً بـ t.results.
CREATE SCHEMA t;
GRANT USAGE ON SCHEMA t TO PUBLIC;
CREATE TABLE t.results (id serial PRIMARY KEY, name text NOT NULL, ok boolean NOT NULL, detail text);
GRANT INSERT ON t.results TO PUBLIC;
GRANT USAGE ON SEQUENCE t.results_id_seq TO PUBLIC;

CREATE FUNCTION t.ok(p_name text, p_cond boolean, p_detail text DEFAULT NULL) RETURNS void
LANGUAGE sql AS $$ INSERT INTO t.results (name, ok, detail) VALUES (p_name, coalesce(p_cond, false), p_detail) $$;

-- ينجح الاختبار فقط إذا رفع التنفيذ خطأً بالرمز/النص المتوقع
CREATE FUNCTION t.raises(p_name text, p_sql text, p_sqlstate text DEFAULT NULL, p_msg text DEFAULT NULL) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
  BEGIN
    EXECUTE p_sql;
  EXCEPTION WHEN OTHERS THEN
    IF (p_sqlstate IS NULL OR SQLSTATE = p_sqlstate) AND (p_msg IS NULL OR SQLERRM ILIKE '%' || p_msg || '%') THEN
      INSERT INTO t.results (name, ok) VALUES (p_name, true);
    ELSE
      INSERT INTO t.results (name, ok, detail) VALUES (p_name, false, 'wrong error: ' || SQLSTATE || ' ' || SQLERRM);
    END IF;
    RETURN;
  END;
  INSERT INTO t.results (name, ok, detail) VALUES (p_name, false, 'expected an error but statement succeeded');
END $$;

CREATE FUNCTION t.scalar(p_sql text) RETURNS text LANGUAGE plpgsql AS $$
DECLARE v text; BEGIN EXECUTE p_sql INTO v; RETURN v; END $$;
