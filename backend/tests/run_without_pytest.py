"""Fallback runner when pytest is not installed: python tests/run_without_pytest.py"""
import importlib.util, os, sys, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
spec = importlib.util.spec_from_file_location("t", os.path.join(os.path.dirname(__file__), "test_pure.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
fail = 0
for n in sorted(dir(mod)):
    if n.startswith("test_"):
        try: getattr(mod, n)(); print("PASS", n)
        except Exception: fail += 1; print("FAIL", n); traceback.print_exc()
sys.exit(1 if fail else 0)
