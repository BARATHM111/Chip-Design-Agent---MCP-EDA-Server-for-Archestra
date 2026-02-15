@echo off
setlocal

:: --- Configuration ---
set "PORT=3334"
set "FILE_PORT=8081"
set /p "MCP_API_KEY=Enter your desired API Key (leave empty for no auth): "

:: Display deployment info
echo.
echo ========================================================
echo   MCP EDA SERVER - LIVE DEPLOYMENT
echo ========================================================
echo.
echo  1. Starting Server on port %PORT%...
echo  2. Starting File Server on port %FILE_PORT%...
if not "%MCP_API_KEY%"=="" (
    echo  3. Authentication Enabled (Key: %MCP_API_KEY%)
) else (
    echo  3. Authentication DISABLED (Public Access)
)
echo.

:: Check for ngrok
where ngrok >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] 'ngrok' is not found in PATH.
    echo Please install ngrok from https://ngrok.com/download
    echo and ensure it is in your system PATH.
    pause
    exit /b 1
)

:: Start ngrok in a separate window
echo Starting ngrok tunnels...
start "Ngrok Tunnels" ngrok http --url=mcp-eda.ngrok.app %PORT%
:: Note: Free ngrok only supports 1 tunnel easily. 
:: We prioritize the MCP server. Users can view files via local IP if needed,
:: or upgrade ngrok account for multiple items.
:: Ideally, we'd use a configuration file for multiple tunnels.

:: Start the Python Server
echo Starting Python Server...
python server.py

endlocal
