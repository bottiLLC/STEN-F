@echo off
chcp 65001 > nul

echo ===================================================
echo  STEN-F Reflex 繧｢繝励Μ繧ｱ繝ｼ繧ｷ繝ｧ繝ｳ襍ｷ蜍輔せ繧ｯ繝ｪ繝励ヨ
echo ===================================================

cd /d "%~dp0"

:: uv 繧ｳ繝槭Φ繝峨・蟄伜惠繝√ぉ繝・け
where uv >nul 2>nul
if errorlevel 1 (
    echo [ERROR] uv 繧ｳ繝槭Φ繝峨′隕九▽縺九ｊ縺ｾ縺帙ｓ縲・    echo [ERROR] Astral-sh 縺ｮ uv 縺後う繝ｳ繧ｹ繝医・繝ｫ縺輔ｌ縲∫腸蠅・､画焚 PATH 縺ｫ騾壹▲縺ｦ縺・ｋ縺狗｢ｺ隱阪＠縺ｦ縺上□縺輔＞縲・    echo [ERROR] 繧､繝ｳ繧ｹ繝医・繝ｫ謇矩・↓縺､縺・※縺ｯ蜈ｬ蠑上ラ繧ｭ繝･繝｡繝ｳ繝医ｒ蜿ら・縺励※縺上□縺輔＞縲・    pause
    exit /b 1
)

:: .venv 縺ｮ蟄伜惠繝√ぉ繝・け縺ｨ蛻晄悄蛹・if not exist ".venv" (
    echo [INFO] 莉ｮ諠ｳ迺ｰ蠅・ｼ・venv・峨′隕九▽縺九ｊ縺ｾ縺帙ｓ縲ょ・譛溯ｨｭ螳壹ｒ髢句ｧ九＠縺ｾ縺・..
    echo [INFO] uv 繧剃ｽｿ逕ｨ縺励※萓晏ｭ倬未菫ゅｒ蜷梧悄縺励※縺・∪縺・..
    uv sync
    if errorlevel 1 (
        echo [ERROR] 迺ｰ蠅・・蛻晄悄蛹悶↓螟ｱ謨励＠縺ｾ縺励◆縲Ｑyproject.toml 繧堤｢ｺ隱阪＠縺ｦ縺上□縺輔＞縲・        pause
        exit /b 1
    )
    echo [INFO] 迺ｰ蠅・ｧ狗ｯ峨′螳御ｺ・＠縺ｾ縺励◆縲・)

:: 繝悶Λ繧ｦ繧ｶ閾ｪ蜍戊ｵｷ蜍包ｼ医ヰ繝・け繧ｰ繝ｩ繧ｦ繝ｳ繝峨〒8遘貞ｾ後↓襍ｷ蜍包ｼ・echo [INFO] 繝悶Λ繧ｦ繧ｶ閾ｪ蜍戊ｵｷ蜍輔ち繧ｹ繧ｯ繧帝幕蟋九＠縺ｦ縺・∪縺・..
start "" cmd /c "timeout /t 8 /nobreak >nul & start http://localhost:3000"

:: 繧｢繝励Μ繧ｱ繝ｼ繧ｷ繝ｧ繝ｳ縺ｮ襍ｷ蜍・echo [INFO] Reflex 繧｢繝励Μ繧ｱ繝ｼ繧ｷ繝ｧ繝ｳ繧定ｵｷ蜍輔＠縺ｦ縺・∪縺・..
uv run reflex run

if errorlevel 1 (
    echo [WARNING] 繧｢繝励Μ繧ｱ繝ｼ繧ｷ繝ｧ繝ｳ縺檎焚蟶ｸ邨ゆｺ・＠縺溘°縲√∪縺溘・蛛懈ｭ｢縺輔ｌ縺ｾ縺励◆縲・    pause
)

