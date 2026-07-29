#!/usr/bin/env python3
import json,pathlib,subprocess,sys,tempfile
helper=pathlib.Path(__file__).resolve().parents[2]/"scenarios/scripts/lib/manifest-git-state.py"
assert helper.exists(),"missing manifest exact-path helper"
with tempfile.TemporaryDirectory() as d:
 root=pathlib.Path(d);subprocess.run(["git","init","-q",root],check=True)
 (root/"a").mkdir();(root/"b").mkdir();(root/"a/result.json").write_text("target");(root/"b/result.json").write_text("other")
 state=json.loads(subprocess.check_output([sys.executable,helper,root,root/"a/result.json"],text=True))
 assert state["dirty"] and state["untracked_count"]==1 and state["excluded_runtime_output"]==["a/result.json"],state
 outside=pathlib.Path(d).parent/"outside-result.json"
 state=json.loads(subprocess.check_output([sys.executable,helper,root,outside],text=True))
 assert state["untracked_count"]==2 and state["excluded_runtime_output"]==[],state
print("M6 manifest exact normalized path contract passed")
