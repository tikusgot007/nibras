import json, os, sys, dataclasses as d
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ps_wrapper as w
print(json.dumps(d.asdict(w.run_ps("$ExecutionContext.SessionState.LanguageMode = 'ConstrainedLanguage'; [System.Math]::Sqrt(4)")), ensure_ascii=False, indent=2))
