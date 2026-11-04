"""Minimal PowerShell 5.1 invocation wrapper for Uji #5 (D-17).

Calls `powershell.exe -NoProfile -NonInteractive -Command <script>` and
classifies failures. The raw stdout/stderr/exit code are ALWAYS kept in the
result for logging; `user_message` is the simplified text for the UI.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from typing import Optional

DEFAULT_TIMEOUT = 15  # seconds; see results/uji05-powershell.md for rationale

MESSAGES = {
    "OK": "",
    "NOT_FOUND": "Windows PowerShell tidak ditemukan di PC ini. Fitur yang membutuhkannya dinonaktifkan.",
    "BLOCKED_BY_POLICY": "PowerShell diblokir oleh kebijakan di PC ini (AppLocker/Group Policy). Fitur yang membutuhkannya dinonaktifkan.",
    "EXEC_POLICY": "Kebijakan eksekusi skrip PowerShell di PC ini melarang skrip dijalankan. Fitur yang membutuhkannya dinonaktifkan.",
    "CONSTRAINED_LANGUAGE": "PowerShell di PC ini berjalan dalam mode terbatas (Constrained Language). Fitur yang membutuhkannya dinonaktifkan.",
    "TIMEOUT": "PowerShell tidak merespons tepat waktu. Coba lagi nanti.",
    "ERROR": "PowerShell mengembalikan kesalahan. Detail ada di log.",
}


@dataclass
class PsResult:
    kind: str
    returncode: Optional[int]
    stdout: str
    stderr: str
    duration_s: float
    user_message: str
    exception: str = ""


def find_powershell(env=None) -> Optional[str]:
    """Preflight: locate powershell.exe on the (possibly overridden) PATH."""
    path = (env or os.environ).get("PATH", "")
    return shutil.which("powershell.exe", path=path)


def classify(returncode, stderr, exc) -> str:
    if isinstance(exc, subprocess.TimeoutExpired):
        return "TIMEOUT"
    if isinstance(exc, FileNotFoundError):
        return "NOT_FOUND"
    if isinstance(exc, OSError):
        # WinError 1260: blocked by group policy; 225: virus/PUA; 5: access denied
        if getattr(exc, "winerror", None) in (1260, 5, 225):
            return "BLOCKED_BY_POLICY"
        return "ERROR"
    if returncode == 0:
        return "OK"
    low = (stderr or "").lower()
    if "blocked by group policy" in low or "applocker" in low:
        return "BLOCKED_BY_POLICY"
    if "pssecurityexception" in low or "running scripts is disabled" in low or "about_execution_policies" in low:
        return "EXEC_POLICY"
    if "constrainedlanguage" in low or "language mode" in low:
        return "CONSTRAINED_LANGUAGE"
    return "ERROR"


def run_ps(script: str, timeout: float = DEFAULT_TIMEOUT, env=None, exe: str = "powershell.exe") -> PsResult:
    t0 = time.monotonic()
    rc, out, err, exc = None, "", "", None
    try:
        if os.path.basename(exe) == exe:
            # Preflight: resolve against the PATH the child will get (Windows
            # CreateProcess otherwise searches the PARENT's PATH, hiding NOT_FOUND).
            resolved = find_powershell(env) if exe.lower() == "powershell.exe" else shutil.which(exe, path=(env or os.environ).get("PATH", ""))
            if resolved is None:
                raise FileNotFoundError(f"{exe} not found on PATH")
            exe = resolved
        p = subprocess.run(
            [exe, "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=timeout, env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        rc, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        exc = e
        out = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = (e.stderr or b"").decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
    except OSError as e:
        exc = e
        err = str(e)
    except Exception as e:  # never let anything reach the UI unhandled
        exc = e
        err = repr(e)
    kind = classify(rc, err, exc)
    return PsResult(kind, rc, out, err, round(time.monotonic() - t0, 3), MESSAGES[kind],
                    exception=repr(exc) if exc else "")


if __name__ == "__main__":
    script = sys.argv[1] if len(sys.argv) > 1 else 'Write-Output "ok"'
    timeout = float(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_TIMEOUT
    print(json.dumps(asdict(run_ps(script, timeout)), ensure_ascii=False, indent=2))
