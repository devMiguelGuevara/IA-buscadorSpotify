@echo off
rem Lanzador del banco de audio para Windows.
rem Doble clic: abre el menu. Arrastrar una lista o pegar su ruta: la descarga.
rem La primera vez crea el entorno de Python e instala lo necesario.
setlocal EnableDelayedExpansion
title Banco de audio
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
set "PYW=.venv\Scripts\pythonw.exe"

if not exist "%PY%" (
    call :preparar
    if errorlevel 1 goto :fin
)

if not "%~1"=="" (
    "%PY%" -m banco_audio descargar "%~1"
    pause
    goto :fin
)

:menu
cls
echo.
echo   ==========================================
echo     BANCO DE AUDIO  -  IA-buscadorSpotify
echo   ==========================================
echo.
echo     1. Abrir el reproductor
echo     2. Descargar una lista, playlist o "guardadas"
echo     3. Probar sin descargar (simulacion)
echo     4. Ver mis playlists de Spotify
echo     5. Exportar una playlist de Spotify a Excel
echo     6. Actualizar yt-dlp
echo     7. Lector rapido
echo     0. Salir
echo.
set "OP="
set /p "OP=  Elige una opcion: "
if not defined OP (
    rem Tres Enter vacios seguidos cierran el menu; evita un bucle si se cierra la entrada.
    set /a VACIOS+=1
    if !VACIOS! GEQ 3 goto :fin
    goto :menu
)
set "VACIOS=0"
if "!OP!"=="1" goto :reproductor
if "!OP!"=="2" goto :descargar
if "!OP!"=="3" goto :simular
if "!OP!"=="4" goto :playlists
if "!OP!"=="5" goto :exportar
if "!OP!"=="6" goto :actualizar
if "!OP!"=="7" goto :lector
if "!OP!"=="0" goto :fin
goto :menu

:pedir_fuente
echo.
echo   Pega la ruta de un Excel, CSV o TXT, un enlace de playlist de Spotify
echo   o escribe guardadas. Tambien puedes arrastrar el archivo a esta ventana.
set "FUENTE="
set /p "FUENTE=  > "
if defined FUENTE set "FUENTE=!FUENTE:"=!"
exit /b 0

:reproductor
start "" "%PYW%" -m banco_audio app
goto :menu

:descargar
call :pedir_fuente
if not defined FUENTE goto :menu
"%PY%" -m banco_audio descargar "!FUENTE!"
pause
goto :menu

:simular
call :pedir_fuente
if not defined FUENTE goto :menu
set "LIM="
set /p "LIM=  Cuantas canciones probar? [5]: "
if not defined LIM set "LIM=5"
"%PY%" -m banco_audio descargar "!FUENTE!" --simular --limite !LIM!
pause
goto :menu

:playlists
"%PY%" -m banco_audio playlists
pause
goto :menu

:exportar
echo.
set "FUENTE="
set /p "FUENTE=  Enlace de la playlist o guardadas: "
if not defined FUENTE goto :menu
set "FUENTE=!FUENTE:"=!"
"%PY%" -m banco_audio exportar "!FUENTE!"
pause
goto :menu

:actualizar
"%PY%" -m pip install -U "yt-dlp[default]"
pause
goto :menu

:lector
start "" "%PYW%" lector\lector_rapido.py
goto :menu

:preparar
echo.
echo   Primera vez: preparando el entorno de Python...
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -m venv .venv
) else (
    python -m venv .venv
)
if not exist "%PY%" (
    echo.
    echo   No se encontro Python 3.10 o superior.
    echo   Instalalo con:  winget install Python.Python.3.13
    echo   Guia completa:  docs\INSTALACION.md
    pause
    exit /b 1
)
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo   Fallo la instalacion de dependencias. Revisa tu conexion y vuelve a abrir el lanzador.
    rmdir /s /q .venv
    pause
    exit /b 1
)
if not exist ".env" copy ".env.example" ".env" >nul
echo.
echo   Listo. Para usar Spotify, completa tus credenciales en el archivo .env
pause
exit /b 0

:fin
endlocal
