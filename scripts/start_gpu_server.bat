@echo off
title DBLP Intel Iris Xe GPU Runner (Vulkan)
echo ===================================================================
echo   Starting Qwen 2.5 Coder on Intel Iris Xe GPU (Vulkan)
echo ===================================================================
echo.
echo Model: Qwen 2.5 Coder 7B (GGUF)
echo Offloading 33 layers directly to Intel Iris Xe GPU...
echo.
cd /d "C:\llama-vulkan"
llama-server.exe -m "C:\Users\user\.ollama\models\blobs\sha256-60e05f2100071479f596b964f89f510f057ce397ea22f2833a0cfe029bfc2463" -ngl 33 --port 8080 -c 2048 -t 8
pause
