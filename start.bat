@echo off
cd /d %~dp0
echo STEN-F 襍ｷ蜍墓ｺ門ｙ荳ｭ...

:: 蛻･繝励Ο繧ｻ繧ｹ縺ｨ縺励※邏・遘貞ｾ・ｩ溷ｾ後↓繝悶Λ繧ｦ繧ｶ繧定ｵｷ蜍輔＆縺帙ｋ・医Γ繧､繝ｳ繝励Ο繧ｻ繧ｹ繧呈ｭ｢繧√↑縺・ｼ・
start "" cmd /c "timeout /t 7 /nobreak >nul && start http://localhost:3000"

uv run reflex run
pause

