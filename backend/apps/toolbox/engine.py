"""
GeoLibre on the server: the engine's WASI program (`geolibre-cli.wasm`, whitebox_next_gen + GeoLibre tools, MIT)
run with wasmtime. The same program runs in the GeoLibre web app; tool ids, parameters and results are the same.

    geolibre <tool> --param=value ... with a /work folder mapped to the run's working folder

The .wasm file is found in this order: settings.GEOLIBRE_WASM; DATA_DIR/engines/geolibre-cli-<version>.wasm;
copied from frontend/node_modules/geolibre-wasm (a developer checkout); downloaded once from the npm CDN.
Compiled modules are cached by wasmtime, so later runs start in a fraction of a second.
"""
import json
import logging
import os
import shutil
import threading
import urllib.request
from pathlib import Path

from django.conf import settings

log = logging.getLogger(__name__)

VERSION = "1.7.1"
CDN_URL = f"https://cdn.jsdelivr.net/npm/geolibre-wasm@{VERSION}/geolibre-cli.wasm"
NAME = f"geolibre {VERSION}"

TIME_LIMIT_S = 600          # a tool run is stopped after this long (settings.TOOLBOX_TIME_LIMIT)

_lock = threading.Lock()
_engine = _module = None
_manifests = None
_ticker = None


class EngineError(Exception):
    pass


def wasm_path():
    custom = getattr(settings, "GEOLIBRE_WASM", "")
    if custom:
        p = Path(custom)
        if not p.exists():
            raise EngineError(f"GEOLIBRE_WASM points to {p}, which doesn't exist.")
        return p
    dest = Path(settings.DATA_DIR) / "engines" / f"geolibre-cli-{VERSION}.wasm"
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    local = Path(settings.BASE_DIR).parent / "frontend" / "node_modules" / "geolibre-wasm" / "geolibre-cli.wasm"
    tmp = dest.with_name(f"{dest.name}.{os.getpid()}-{threading.get_ident()}.part")  # unique: two workers may fetch it at once
    if local.exists():
        shutil.copyfile(local, tmp)
    else:
        log.info("Downloading the GeoLibre engine from %s", CDN_URL)
        try:
            with urllib.request.urlopen(CDN_URL, timeout=120) as r, open(tmp, "wb") as f:
                shutil.copyfileobj(r, f)
        except OSError as exc:
            raise EngineError(f"The processing engine couldn't be downloaded ({exc}). Copy geolibre-cli.wasm "
                              f"{VERSION} to {dest} or set GEOLIBRE_WASM.") from None
    tmp.replace(dest)
    return dest


def _load():
    global _engine, _module
    with _lock:
        if _module is None:
            try:
                from wasmtime import Config, Engine, Module
            except ImportError:
                raise EngineError("The processing engine needs the wasmtime package (pip install wasmtime).") from None
            cfg = Config()
            cfg.cache = True
            cfg.epoch_interruption = True       # lets a run be stopped after its time limit
            _engine = Engine(cfg)
            _module = Module.from_file(_engine, str(wasm_path()))
            _start_ticker(_engine)
            import atexit
            atexit.register(_release)
    return _engine, _module


def _release():
    """Free the engine before Python shuts down (wasmtime's own cleanup fails once its library is unloaded)."""
    global _engine, _module
    _module = _engine = None
    import gc
    gc.collect()


def _start_ticker(engine_):
    """Advance the engine's epoch once a second; each run's deadline is its time limit in epochs."""
    global _ticker
    import time

    def tick():
        while True:
            time.sleep(1)
            engine_.increment_epoch()
    _ticker = threading.Thread(target=tick, name="geolibre-epoch", daemon=True)
    _ticker.start()


class TimeLimit(EngineError):
    pass


def run(argv, workdir, timeout_s=None):
    """
    Run `geolibre <argv...>` with /work mapped to workdir. Returns (exit code, output lines). Raises EngineError
    when the engine can't start, TimeLimit when the tool runs longer than its limit; a tool that fails returns a
    non-zero code with its message in the lines.
    """
    from wasmtime import ExitTrap, Linker, Store, Trap, WasiConfig, WasmtimeError
    engine, module = _load()
    workdir = Path(workdir)
    out, err = workdir / ".stdout", workdir / ".stderr"
    store = Store(engine)
    limit = int(timeout_s or getattr(settings, "TOOLBOX_TIME_LIMIT", 0) or TIME_LIMIT_S)
    store.set_epoch_deadline(limit)
    wasi = WasiConfig()
    wasi.argv = ["geolibre", *argv]
    wasi.preopen_dir(str(workdir), "/work")
    wasi.stdout_file, wasi.stderr_file = str(out), str(err)
    store.set_wasi(wasi)
    linker = Linker(engine)
    linker.define_wasi()
    inst = linker.instantiate(store, module)
    code = 0
    try:
        inst.exports(store)["_start"](store)
    except ExitTrap as exc:
        code = exc.code
    except (Trap, WasmtimeError) as exc:
        if "interrupt" in str(exc).lower() or getattr(exc, "trap_code", None) == getattr(__import__("wasmtime").TrapCode, "INTERRUPT", -2):
            for f in (out, err):
                f.unlink(missing_ok=True)
            span = f"{limit // 60} minutes" if limit >= 120 else f"{limit} seconds"
            raise TimeLimit(f"The tool ran for more than {span} and was stopped. Try a smaller or simpler input "
                            "(e.g. fewer or simpler polygons).") from None
        code = -1
        err.write_text((err.read_text() if err.exists() else "") + f"\nThe tool stopped: {exc}".split("\nwasm backtrace")[0])
    lines = []
    for f in (out, err):
        if f.exists():
            lines += [ln for ln in f.read_text(errors="replace").splitlines() if ln.strip()]
            f.unlink()
    return code, lines


def last_json(lines):
    """The tool's result object (its last JSON line), or {}."""
    for ln in reversed(lines):
        ln = ln.strip()
        if ln.startswith("{"):
            try:
                return json.loads(ln)
            except ValueError:
                continue
    return {}


def manifests():
    """{tool id: manifest} for every engine tool (cached in DATA_DIR/engines)."""
    global _manifests
    if _manifests is not None:
        return _manifests
    cache = Path(settings.DATA_DIR) / "engines" / f"geolibre-{VERSION}-manifests.json"
    if not cache.exists():
        import tempfile
        with tempfile.TemporaryDirectory(prefix="geolibre-") as tmp:
            code, lines = run(["manifests"], tmp)
        if code != 0:
            raise EngineError("The processing engine couldn't list its tools.")
        text = "".join(ln for ln in lines if not ln.startswith("running"))
        json.loads(text)  # validate before caching
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(text)
    _manifests = {m["id"]: m for m in json.loads(cache.read_text())}
    return _manifests
