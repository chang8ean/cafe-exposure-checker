# 매일 07:30 판정 · 13:30 이어서(--resume) 를 작업 스케줄러에 등록한다.
# 사용(PowerShell):  powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1
# 해제:              powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1 -Uninstall
param([switch]$Uninstall)
$Repo = (Resolve-Path "$PSScriptRoot\..").Path
$Py = Join-Path $Repo ".venv\Scripts\python.exe"
New-Item -ItemType Directory -Force -Path (Join-Path $Repo "logs") | Out-Null

$jobs = @(
  @{ Name = "CafeExposureChecker-Morning";   At = "07:30"; Arg = "";         Log = "morning.log" },
  @{ Name = "CafeExposureChecker-Afternoon"; At = "13:30"; Arg = "--resume"; Log = "afternoon.log" }
)
foreach ($j in $jobs) {
  Unregister-ScheduledTask -TaskName $j.Name -Confirm:$false -ErrorAction SilentlyContinue
  if ($Uninstall) { Write-Host "해제: $($j.Name)"; continue }
  $cmd = "/c set PYTHONIOENCODING=utf-8 && `"$Py`" `"$Repo\run.py`" $($j.Arg) >> `"$Repo\logs\$($j.Log)`" 2>&1"
  $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $cmd -WorkingDirectory $Repo
  $trigger = New-ScheduledTaskTrigger -Daily -At $j.At
  # 꺼져 있다 켜지면 놓친 실행을 한 번 돌린다
  $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 3)
  Register-ScheduledTask -TaskName $j.Name -Action $action -Trigger $trigger -Settings $settings | Out-Null
  Write-Host "등록: $($j.Name) ($($j.At))"
}
