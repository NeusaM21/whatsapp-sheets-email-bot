param(
  [switch]$OpenSheet,          # abre a planilha após o teste
  [switch]$EmailReal,          # valida se .env está pronto p/ envio real
  [string]$BaseUrl,            # override do endpoint (ex: http://localhost:5000)
  [string]$From,               # telefone de teste
  [string]$Name,               # nome de teste
  [string]$Message,            # mensagem de teste
  [string]$LeadEmail           # opcional: inclui e-mail do lead no corpo
)

# --- util: parser de .env (remove comentários inline) -------------------------
function Get-DotEnv([string]$Path = ".env") {
  $h = @{}
  if (Test-Path $Path) {
    foreach ($line in Get-Content $Path) {
      if ($line -match '^\s*#' -or $line -match '^\s*$') { continue }
      if ($line -match '^\s*([^=]+?)\s*=\s*(.*)\s*$') {
        $k = $matches[1].Trim()
        $v = $matches[2].Trim()

        # Se estiver entre aspas, só tira as aspas. Caso contrário, remove comentário inline.
        if ($v.StartsWith('"') -and $v.EndsWith('"')) {
          $v = $v.Substring(1, $v.Length - 2)
        }
        elseif ($v.StartsWith("'") -and $v.EndsWith("'")) {
          $v = $v.Substring(1, $v.Length - 2)
        }
        else {
          if ($v -match '^(.*?)(\s*#.*)$') { $v = $matches[1] }
          $v = $v.Trim()
        }
        $h[$k] = $v
      }
    }
  }
  return $h
}

function To-Bool([string]$v, [bool]$default = $false) {
  if ([string]::IsNullOrWhiteSpace($v)) { return $default }
  $on = @('1', 'true', 'yes', 'on')
  return $on -contains $v.Trim().ToLower()
}

$envs = Get-DotEnv

# --- BaseUrl (NÃO usar $Host: é reservado no PowerShell) ----------------------
if (-not $BaseUrl) {
  $ServerHost = $envs['HOST']; if (-not $ServerHost) { $ServerHost = '127.0.0.1' }
  $ServerPort = $envs['PORT']; if (-not $ServerPort) { $ServerPort = '5000' }
  $BaseUrl = 'http://{0}:{1}' -f $ServerHost, $ServerPort
}
Write-Host "BaseUrl: $BaseUrl" -ForegroundColor DarkGray

# --- Defaults de teste --------------------------------------------------------
if (-not $From) { $From = $envs['TEST_WHATSAPP_FROM']; if (-not $From) { $From = '5511999999999' } }
if (-not $Name) { $Name = $envs['TEST_CONTACT_NAME']; if (-not $Name) { $Name = 'Neusa Teste' } }
if (-not $Message) { $Message = $envs['TEST_MESSAGE']; if (-not $Message) { $Message = 'Olá, quero orçamento' } }
if ($LeadEmail) { $Message = "$Message ($LeadEmail)" }

# --- /status ------------------------------------------------------------------
Write-Host ">> /status" -ForegroundColor Cyan
try {
  $status = Invoke-RestMethod -Uri "$BaseUrl/status" -Method GET -TimeoutSec 5
  $status | ConvertTo-Json -Depth 8
}
catch {
  Write-Warning "Falhou GET /status: $($_.Exception.Message)"
}

# --- payload de teste ---------------------------------------------------------
$WAMID = "wamid.TEST.$(Get-Date -Format yyyyMMddHHmmss)"
Write-Host ">> WAMID = $WAMID" -ForegroundColor Yellow

$payload = @{
  entry = @(
    @{
      changes = @(
        @{
          value = @{
            messages = @(@{ id = $WAMID; from = $From; text = @{ body = $Message } })
            contacts = @(@{ profile = @{ name = $Name } })
          }
        }
      )
    }
  )
} | ConvertTo-Json -Depth 10

# --- POST /webhook ------------------------------------------------------------
Write-Host ">> POST /webhook" -ForegroundColor Cyan
try {
  $resp = Invoke-RestMethod -Uri "$BaseUrl/webhook" -Method POST -ContentType "application/json" -Body $payload
  $resp | ConvertTo-Json -Depth 8
}
catch {
  Write-Warning "Falhou POST /webhook: $($_.Exception.Message)"
  return
}

# --- Checagem opcional de envio real -----------------------------------------
if ($EmailReal) {
  $enabled = To-Bool $envs['EMAIL_ENABLED'] $false
  $dry = To-Bool $envs['EMAIL_DRY_RUN'] $true

  if (-not $enabled -or $dry) {
    Write-Warning "Para ENVIO REAL: ajuste no .env -> EMAIL_ENABLED=1 e EMAIL_DRY_RUN=0 (atual: EMAIL_ENABLED=$($envs['EMAIL_ENABLED']), EMAIL_DRY_RUN=$($envs['EMAIL_DRY_RUN']))"
  }
  else {
    Write-Host "OK: envio real habilitado (.env já está EMAIL_ENABLED=1 / EMAIL_DRY_RUN=0)." -ForegroundColor Green
  }
}

# --- Abrir planilha -----------------------------------------------------------
if ($OpenSheet) {
  $sheetUrl = $envs['SHEET_URL']
  if (-not $sheetUrl) {
    $sid = $envs['SHEET_ID']
    if ($sid) { $sheetUrl = "https://docs.google.com/spreadsheets/d/$sid/edit" }
  }
  if ($sheetUrl) { Start-Process $sheetUrl } else { Write-Warning "Não encontrei SHEET_URL nem SHEET_ID no .env" }
}