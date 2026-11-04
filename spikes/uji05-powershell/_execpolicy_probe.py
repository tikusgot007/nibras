import dataclasses as d, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ps_wrapper as w
here = os.path.dirname(os.path.abspath(__file__))
print("inline:", json.dumps(d.asdict(w.run_ps("Write-Output ok")), ensure_ascii=False))
print("script:", json.dumps(d.asdict(w.run_ps("& '%s'" % os.path.join(here, "noop.ps1"))), ensure_ascii=False))
