@echo off
title AnyDownloader - GitHub Sign-in
echo.
echo ============================================================
echo   AnyDownloader needs GitHub access to create the repo
echo   and push. A browser window will open in a moment.
echo   Please sign in to GitHub and approve the request.
echo ============================================================
echo.
set GCM_INTERACTIVE=force
(echo protocol=https
 echo host=github.com
 echo.) | git credential fill >nul 2>&1
if %errorlevel%==0 (
  echo AUTH SUCCESS - credentials stored in Windows Credential Manager.
  echo You can close this window and return to ZCode.
) else (
  echo AUTH FAILED - the sign-in did not complete.
  echo Close this window and tell ZCode to retry.
)
pause
