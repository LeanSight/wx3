@echo off
title wx4 - Bci Seguros Data
set "WX4=d:\workspace\#dev\wx3"
set "REC=C:\workspace\@recordings\20260225 Bci Seguros Data"

cd /d "%WX4%"

echo.
echo === wx4: Bci Seguros Data - 6 archivos ===
echo Enhance (ClearVoice) + Transcribe (AssemblyAI) + Video output
echo.

python -m wx4 "%REC%\20260225_105002.mp4" "%REC%\20260225_110533.mp4" "%REC%\20260225_124916.mp4" "%REC%\20260225_125752.mp4" "%REC%\20260225_130730.mp4" "%REC%\Voz 260225_091512.m4a" --videooutput

echo.
echo === Proceso finalizado ===
pause
