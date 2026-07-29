#!/usr/bin/env python3
import json, pathlib, subprocess, sys

root=pathlib.Path(sys.argv[1]).resolve();target=pathlib.Path(sys.argv[2]).resolve() if len(sys.argv)>2 and sys.argv[2] else None
lines=subprocess.check_output(["git","-C",root,"status","--porcelain=v1","--untracked-files=all"],text=True).splitlines()
tracked=any(not line.startswith("?? ") for line in lines);untracked=[line[3:] for line in lines if line.startswith("?? ")];excluded=[]
if target is not None:
    try: relative=target.relative_to(root).as_posix()
    except ValueError: relative=None
    if relative is not None:
        target_path=pathlib.PurePosixPath(relative);untracked=[path for path in untracked if path!=relative and not (pathlib.PurePosixPath(path).parent==target_path.parent and pathlib.PurePosixPath(path).name.startswith(".tmp."))];excluded=[relative]
print(json.dumps({"dirty":tracked or bool(untracked),"tracked_dirty":tracked,"untracked_count":len(untracked),"excluded_runtime_output":excluded},separators=(",",":")))
