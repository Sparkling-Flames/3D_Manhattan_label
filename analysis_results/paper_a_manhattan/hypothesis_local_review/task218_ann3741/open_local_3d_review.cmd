@echo off
setlocal
for %%I in ("%~dp0..\..\..\..") do set "REPO_ROOT=%%~fI"
cd /d "%REPO_ROOT%"
python tools\paper_a_manhattan\serve_local_3d_projection_review.py --repo-root "%REPO_ROOT%" --review "analysis_results\paper_a_manhattan\hypothesis_local_review\task218_ann3741\local_3d_review.html"
if errorlevel 1 pause
