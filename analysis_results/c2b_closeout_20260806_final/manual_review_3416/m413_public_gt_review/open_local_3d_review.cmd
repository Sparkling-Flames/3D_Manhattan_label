@echo off
setlocal
for %%I in ("%~dp0..\..\..\..") do set "REPO_ROOT=%%~fI"
cd /d "%REPO_ROOT%"
python tools\paper_a_manhattan\serve_local_3d_projection_review.py --repo-root "%REPO_ROOT%" --review "analysis_results\c2b_closeout_20260806_final\manual_review_3416\m413_public_gt_review\local_3d_review.html"
if errorlevel 1 pause
