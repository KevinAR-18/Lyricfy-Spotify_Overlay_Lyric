"""Non-blocking, cached UI Automation fallback for Windows 11 taskbar controls."""
import base64
import json
import subprocess
import threading
import time


_cache = {}
_pending = set()
_lock = threading.Lock()


def cached_controls(hwnd: int):
    """Return the last result immediately; native accessibility runs off the UI thread."""
    with _lock:
        stamp, result = _cache.get(hwnd, (0, None))
        if hwnd not in _pending and time.monotonic() - stamp > 5:
            _pending.add(hwnd)
            threading.Thread(target=_query, args=(hwnd,), daemon=True).start()
        return result


def _query(hwnd: int):
    script = r"""
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]HWND_VALUE)
$all = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
$items = @()
foreach ($el in $all) {
    try {
        $c = $el.Current
        $r = $c.BoundingRectangle
        if ($c.IsOffscreen -or $r.Width -le 0 -or $r.Height -le 0) { continue }
        $id = $c.AutomationId
        $isStart = $id -match '^(StartButton|Start)$'
        if ($isStart -or $c.ControlType -eq [System.Windows.Automation.ControlType]::Button) {
            $items += @{ start=$isStart; left=$r.Left; top=$r.Top; right=$r.Right; bottom=$r.Bottom }
        }
    } catch {}
}
ConvertTo-Json -InputObject @($items) -Compress
""".replace("HWND_VALUE", str(int(hwnd)))
    result = None
    try:
        encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            capture_output=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode == 0:
            data = json.loads(completed.stdout.decode("utf-8-sig"))
            if isinstance(data, list):
                result = data
    except (OSError, subprocess.TimeoutExpired, ValueError):
        pass
    finally:
        with _lock:
            _cache[hwnd] = (time.monotonic(), result)
            _pending.discard(hwnd)
