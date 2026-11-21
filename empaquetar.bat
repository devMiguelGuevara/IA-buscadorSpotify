@echo off
rem Empaqueta MigueWamp como aplicacion de Windows en dist\MigueWamp\MigueWamp.exe
rem y deja dist\MigueWamp.zip listo para compartir.
rem Requiere el entorno .venv con las dependencias (y Node para compilar la interfaz).
rem ffmpeg, ffprobe y node se copian de este equipo al paquete: quien lo reciba no instala nada.
rem
rem Seguridad de tus datos: PyInstaller construye en build\salida (nunca en dist). Despues
rem solo se reemplazan los archivos del programa en dist\MigueWamp (MigueWamp.exe, _internal,
rem bin y .env.example). Tu musica, ajustes, playlists, .env, versiones y cache no se tocan.
setlocal
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
set "DIST=dist\MigueWamp"
set "NUEVO=build\salida\MigueWamp"

rem Con MigueWamp abierto no se puede reemplazar el programa: se avisa antes de tocar nada.
tasklist /FI "IMAGENAME eq MigueWamp.exe" 2>nul | find /I "MigueWamp.exe" >nul
if not errorlevel 1 (
    echo   MigueWamp esta abierto. Cierralo y vuelve a ejecutar empaquetar.bat.
    goto :error
)

if not exist "%PY%" (
    echo   Falta el entorno .venv. Ejecuta primero iniciar.bat para crearlo.
    goto :error
)

echo [1/6] Herramientas de empaquetado...
"%PY%" -m pip install -q pyinstaller pillow || goto :error

echo [2/6] Compilando la interfaz...
pushd web
call npm install --no-audit --no-fund --loglevel=error || (popd & goto :error)
call npm run build || (popd & goto :error)
popd

echo [3/6] Icono...
"%PY%" empaquetado\crear_icono.py || goto :error

echo [4/6] Empaquetando...
if exist build rmdir /s /q build
"%PY%" -m PyInstaller --noconfirm --clean --distpath build\salida --workpath build\trabajo empaquetado\MigueWamp.spec || goto :error
copy /y ".env.example" "%NUEVO%\.env.example" >nul
rem La skin "Cabeza" va dibujada en vectores dentro de la app: no se incluye ningun .wal

echo [5/6] ffmpeg, ffprobe y node...
mkdir "%NUEVO%\bin"
set "FALTA="
call :copiar ffmpeg.exe
call :copiar ffprobe.exe
call :copiar node.exe
for /f "delims=" %%F in ('where ffmpeg.exe 2^>nul') do (
    if exist "%%~dpF..\LICENSE" copy /y "%%~dpF..\LICENSE" "%NUEVO%\bin\LICENSE-ffmpeg.txt" >nul
    goto :licencia_lista
)
:licencia_lista

echo [6/6] Comprimiendo para compartir y actualizando %DIST%...
if not exist dist mkdir dist
if exist "dist\MigueWamp.zip" del /q "dist\MigueWamp.zip"
rem El zip sale de la construccion limpia: nunca lleva tus datos.
powershell -NoProfile -Command "Compress-Archive -Path '%NUEVO%' -DestinationPath 'dist\MigueWamp.zip'" || goto :error
rem Solo se reemplaza lo que es del programa; el resto de la carpeta queda igual.
if exist "%DIST%\_internal" rmdir /s /q "%DIST%\_internal"
if exist "%DIST%\_internal" (
    echo   No se pudo reemplazar %DIST%\_internal: cierra MigueWamp y vuelve a intentarlo.
    goto :error
)
robocopy "%NUEVO%" "%DIST%" /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto :error
rmdir /s /q build

echo.
echo   Listo: %DIST%\MigueWamp.exe
echo   Para compartir: dist\MigueWamp.zip  (se descomprime y se abre MigueWamp.exe)
if defined FALTA echo   Aviso: no se encontro%FALTA% en este equipo; el paquete no lo incluye.
echo   Copia tu .env a esa carpeta si usas Spotify.
pause
exit /b 0

:copiar
for /f "delims=" %%F in ('where %1 2^>nul') do (
    copy /y "%%F" "%NUEVO%\bin\%1" >nul
    exit /b 0
)
set "FALTA=%FALTA% %1"
exit /b 0

:error
echo.
echo   Fallo el empaquetado. Revisa los mensajes de arriba.
echo   Tus datos en %DIST% no se tocaron.
pause
exit /b 1
