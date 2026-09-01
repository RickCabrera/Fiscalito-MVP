param([int]$MaxTareas = 14)
$log = "docs/nocturno-$(Get-Date -Format 'yyyyMMdd-HHmm').txt"
for ($i = 1; $i -le $MaxTareas; $i++) {
  Write-Host "=== Tarea $i de $MaxTareas — $(Get-Date -Format 'HH:mm') ===" | Tee-Object -Append $log
  git checkout main 2>$null; git pull 2>$null
  $pendientes = (Get-Content backlog.md -Raw) -match '## Cola nocturna'
  claude -p "MODO AUTÓNOMO. Lee CLAUDE.md (sección Modo autónomo), backlog.md y docs/nocturno-log.md. Ejecuta la siguiente tarea de la Cola nocturna siguiendo el protocolo al pie de la letra. Una sola tarea. Termina la sesión al cerrarla o al saltarla." --dangerously-skip-permissions 2>&1 | Tee-Object -Append $log
  if ($LASTEXITCODE -ne 0) { Write-Host "claude salió con error, espero 5 min" | Tee-Object -Append $log; Start-Sleep 300 }
  Start-Sleep 30
}
Write-Host "=== Loop terminado $(Get-Date -Format 'HH:mm') ===" | Tee-Object -Append $log
