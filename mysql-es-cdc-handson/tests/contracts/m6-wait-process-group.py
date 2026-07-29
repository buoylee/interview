#!/usr/bin/env python3
import json, os, pathlib, signal, subprocess, sys, tempfile, time

wait = pathlib.Path(__file__).resolve().parents[2] / "scenarios/scripts/wait-condition.sh"
child_code = r'''import os,signal,sys,time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
pid=os.fork()
if pid==0:
 signal.signal(signal.SIGTERM, signal.SIG_IGN)
 open(sys.argv[1]+".desc","w").write(str(os.getpid()))
 while True: time.sleep(1)
open(sys.argv[1],"w").write(str(os.getpid()))
while True: time.sleep(1)
'''

def dead(pid):
    try: os.kill(pid, 0); return False
    except ProcessLookupError: return True

with tempfile.TemporaryDirectory() as directory:
    marker = str(pathlib.Path(directory) / "pid")
    started=time.monotonic()
    try:
        result=subprocess.run([wait,"tree timeout","1","0.8",sys.executable,"-c",child_code,marker],text=True,capture_output=True,timeout=5)
    except subprocess.TimeoutExpired:
        raise AssertionError("wait-condition blocked while TERM-ignoring process tree survived")
    assert result.returncode == 124, result
    assert time.monotonic()-started < 4
    diagnostic=json.loads(result.stderr.strip().splitlines()[-1])
    assert diagnostic["status"] == "TIMEOUT" and diagnostic["last_exit_code"] == 124
    for path in (marker, marker+".desc"):
        pid=int(pathlib.Path(path).read_text())
        for _ in range(30):
            if dead(pid): break
            time.sleep(.05)
        assert dead(pid), f"surviving pid {pid}"

for sig, expected in ((signal.SIGINT,130),(signal.SIGTERM,143)):
    with tempfile.TemporaryDirectory() as directory:
        marker=str(pathlib.Path(directory)/"pid")
        process=subprocess.Popen([wait,"external signal","30","1",sys.executable,"-c",child_code,marker],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        for _ in range(50):
            if pathlib.Path(marker+".desc").exists(): break
            time.sleep(.05)
        started=time.monotonic();os.kill(process.pid,sig);out,err=process.communicate(timeout=4)
        assert process.returncode == expected,(process.returncode,err)
        assert time.monotonic()-started < 3
        for path in (marker,marker+".desc"):
            pid=int(pathlib.Path(path).read_text())
            for _ in range(30):
                if dead(pid): break
                time.sleep(.05)
            assert dead(pid),f"surviving pid {pid} after signal {sig}"
print("M6 wait process-group contract passed")
