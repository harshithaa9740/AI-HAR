# AURAVISION Local HTTP Web Server
param(
    [int]$Port = 8080
)

$rootDir = $PSScriptRoot
if (-not $rootDir) { $rootDir = Get-Location }

$mimeMap = @{
    ".html" = "text/html; charset=utf-8"
    ".htm"  = "text/html; charset=utf-8"
    ".css"  = "text/css"
    ".js"   = "application/javascript"
    ".json" = "application/json"
    ".png"  = "image/png"
    ".jpg"  = "image/jpeg"
    ".jpeg" = "image/jpeg"
    ".svg"  = "image/svg+xml"
    ".mp4"  = "video/mp4"
    ".ico"  = "image/x-icon"
}

# Create HTTP Listener
$listener = New-Object System.Net.HttpListener
$prefix = "http://localhost:$Port/"
$listener.Prefixes.Add($prefix)

try {
    $listener.Start()
} catch {
    Write-Warning "Port $Port may be in use. Trying port 8085..."
    $Port = 8085
    $prefix = "http://localhost:$Port/"
    $listener = New-Object System.Net.HttpListener
    $listener.Prefixes.Add($prefix)
    $listener.Start()
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   AURAVISION Offline AI Sequence Validator (SIH)" -ForegroundColor Yellow
Write-Host "   Local Server running at: $prefix" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

# Open default browser
try {
    Start-Process $prefix
} catch {}

try {
    while ($listener.IsListening) {
        $context = $listener.GetContext()
        $request = $context.Request
        $response = $context.Response

        $urlPath = $request.Url.LocalPath.TrimStart('/')
        if ([string]::IsNullOrWhiteSpace($urlPath) -or $urlPath -eq "/") {
            $urlPath = "index.html"
        }

        # URL decode path and sanitize
        $urlPath = [System.Uri]::UnescapeDataString($urlPath).Replace('/', [System.IO.Path]::DirectorySeparatorChar)
        $filePath = [System.IO.Path]::Combine($rootDir, $urlPath)

        if ([System.IO.File]::Exists($filePath)) {
            $ext = [System.IO.Path]::GetExtension($filePath).ToLower()
            $contentType = if ($mimeMap.ContainsKey($ext)) { $mimeMap[$ext] } else { "application/octet-stream" }
            $response.ContentType = $contentType
            $response.AddHeader("Accept-Ranges", "bytes")
            $response.AddHeader("Access-Control-Allow-Origin", "*")

            try {
                $fileBytes = [System.IO.File]::ReadAllBytes($filePath)
                $response.ContentLength64 = $fileBytes.Length
                $response.OutputStream.Write($fileBytes, 0, $fileBytes.Length)
            } catch {
                # Client connection closed early
            }
        } else {
            $response.StatusCode = 404
            $errBytes = [System.Text.Encoding]::UTF8.GetBytes("404 Not Found: $urlPath")
            $response.OutputStream.Write($errBytes, 0, $errBytes.Length)
        }

        try {
            $response.Close()
        } catch {}
    }
} finally {
    $listener.Stop()
    $listener.Close()
}
