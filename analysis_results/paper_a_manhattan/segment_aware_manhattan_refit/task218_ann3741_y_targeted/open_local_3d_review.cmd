@echo off
setlocal
for %%I in ("%~dp0..\..\..\..") do set "REPO_ROOT=%%~fI"
cd /d "%REPO_ROOT%"
python tools\paper_a_manhattan\serve_local_3d_projection_review.py --repo-root "%REPO_ROOT%" --review "analysis_results\paper_a_manhattan\segment_aware_manhattan_refit\task218_ann3741_y_targeted\local_3d_review.html"
if errorlevel 1 pause
