"""Black-box local integration, failed release and recovery drill."""
import concurrent.futures
import json
import os
from pathlib import Path
import socket
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

def get(port, path='/'):
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}', timeout=3) as r:
            return r.status, r.read().decode(), time.perf_counter() - start
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), time.perf_counter() - start

def launch(fault=False):
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
    p = subprocess.Popen([sys.executable, str(ROOT/'app.py')],
        env={**os.environ, 'HOST':'127.0.0.1', 'PORT':str(port),
             'DEMO_FAIL_REQUESTS':str(int(fault)), 'APP_VERSION':'bad' if fault else 'good'},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic()+5
    while time.monotonic() < deadline:
        if p.poll() is not None:
            raise AssertionError('App exited on startup')
        try:
            if get(port, '/readyz')[0] == 200:
                return p, port
        except OSError:
            time.sleep(0.02)
    p.kill(); p.wait()
    raise AssertionError('Startup timed out')

def stop(p):
    p.terminate()
    try:
        p.wait(timeout=5)
    except subprocess.TimeoutExpired:
        p.kill(); p.wait()
        raise AssertionError('Graceful shutdown timed out')
    assert p.returncode == 0, f'Unexpected shutdown code {p.returncode}'

results={}
p, port=launch()
try:
    assert get(port)[0] == 200
    assert json.loads(get(port)[1])['version'] == 'good'
    assert get(port, '/healthz')[0] == 200
    assert get(port, '/not-found')[0] == 404
    started=time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        samples=list(pool.map(lambda _: get(port), range(100)))
    assert all(x[0] == 200 for x in samples)
    results['sample']={'requests':100,'concurrency':4,'errors':0,
        'elapsed_seconds':round(time.perf_counter()-started,4),
        'p95_ms':round(sorted(x[2]*1000 for x in samples)[94],3)}
    assert 'demo_requests_total{status="200"} 102' in get(port,'/metrics')[1]
    results['healthy_release']='PASS'
finally:
    stop(p)
p,port=launch(fault=True)
try:
    assert get(port,'/healthz')[0] == 200
    assert get(port,'/readyz')[0] == 200
    assert get(port)[0] == 503
    assert 'demo_requests_total{status="503"} 1' in get(port,'/metrics')[1]
    results['failed_release_detected_by_business_smoke_test']='PASS'
finally:
    stop(p)
start=time.perf_counter()
p,port=launch()
try:
    assert get(port)[0] == 200
    assert json.loads(get(port)[1])['version'] == 'good'
    results['recovery']='PASS'
    results['local_restart_recovery_seconds']=round(time.perf_counter()-start,4)
finally:
    stop(p)
results['sigterm_shutdown_all_three_processes']='PASS'
print(json.dumps(results,indent=2))
