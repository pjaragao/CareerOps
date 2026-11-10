-- 2026-11-10: more jobs a day. Three search rounds of up to 10 searches and more ads read; a limit you changed in the app stays.
UPDATE public.automation_limits SET step0 = 30, step1 = 30, step2 = 30 WHERE kind = 'search' AND (step0, step1, step2) = (12, 12, 12);
UPDATE public.automation_limits SET step0 = 100, step1 = 100, step2 = 100 WHERE kind = 'job_read' AND (step0, step1, step2) = (40, 40, 40);
