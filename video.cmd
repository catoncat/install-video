@echo off
rem Install-video tool (Windows). Usage:
rem   video setup                          first run: install Blender via winget if missing, then Pillow
rem   video make <product> preview [05a]   render a video
rem   video compose <product>              redo subtitles + encoding only
setlocal enabledelayedexpansion

if defined BLENDER goto :run
for /f "delims=" %%B in ('where blender 2^>nul') do if not defined BLENDER set "BLENDER=%%B"
if not defined BLENDER (
  for /d %%D in ("%ProgramFiles%\Blender Foundation\Blender*") do if exist "%%D\blender.exe" set "BLENDER=%%D\blender.exe"
)
if not defined BLENDER (
  for /d %%D in ("%LocalAppData%\Programs\Blender Foundation\Blender*") do if exist "%%D\blender.exe" set "BLENDER=%%D\blender.exe"
)
if not defined BLENDER (
  if /i "%~1"=="setup" (
    echo Blender not found, installing with winget ...
    winget install -e --id BlenderFoundation.Blender --accept-package-agreements --accept-source-agreements || exit /b 1
    for /d %%D in ("%ProgramFiles%\Blender Foundation\Blender*") do if exist "%%D\blender.exe" set "BLENDER=%%D\blender.exe"
  )
)
if not defined BLENDER (
  echo Blender not found. Run "video setup", or install Blender 4.4+ and set BLENDER=path\to\blender.exe
  exit /b 1
)

:run
"%BLENDER%" -b --factory-startup --python-exit-code 1 -P "%~dp0engine\cli.py" -- %*
exit /b %errorlevel%
