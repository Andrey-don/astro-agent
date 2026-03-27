@echo off
set SCRIPT_DIR=%~dp0
set SHORTCUT=%USERPROFILE%\Desktop\Астро-Бот.lnk
set TARGET=%SCRIPT_DIR%Запустить бота.bat

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '%TARGET%'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Description = 'Запустить Астро-Бота'; $s.Save()"

echo Ярлык создан на рабочем столе!
pause
