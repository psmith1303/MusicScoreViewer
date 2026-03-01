@echo off
setlocal

:: ---------------------------------------------------------------
:: Build configuration
:: ---------------------------------------------------------------
set APP_NAME=MusicScoreViewer
set SCRIPT=MusicScoreViewer.py
set ICON=icon.ico

:: Output folders (kept out of the source tree)
set DIST_DIR=dist
set BUILD_DIR=build

:: ---------------------------------------------------------------
:: Build
:: ---------------------------------------------------------------
echo.
echo Building %APP_NAME% ...
echo.

pyinstaller ^
    --noconsole ^
    --onefile ^
    --clean ^
    --name "%APP_NAME%" ^
    --distpath "%DIST_DIR%" ^
    --workpath "%BUILD_DIR%" ^
    --specpath "%BUILD_DIR%" ^
    --icon "%ICON%" ^
    --hidden-import "PIL._tkinter_finder" ^
    --hidden-import "pymupdf" ^
    --collect-submodules "pymupdf" ^
    %SCRIPT% ^
    || pause

:: ---------------------------------------------------------------
:: Done
:: ---------------------------------------------------------------
echo.
echo Done. Executable is in %DIST_DIR%\%APP_NAME%.exe
echo.
pause
