@echo off
chcp 65001 >nul
if not exist "%~dp0launch.ps1" (
  echo 请先把压缩包全部解压到一个文件夹，再双击这个文件。不能在压缩包里直接运行。
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0launch.ps1"
if errorlevel 1 (
  echo 启动失败。请用 Edge 或 Chrome 打开这个文件夹里的 index.html。
  pause
)
