#!/usr/bin/env python3
"""Start the private local app. Uses locked dependencies; no hosting or Docker required."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import venv
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("CAREERPILOT_DATA_DIR", str(ROOT / "data"))).resolve()
PRIVATE = DATA / "private"
LOCK = PRIVATE / "runner.lock"
WIN = os.name == "nt"
CHILDREN: list[subprocess.Popen] = []


def python_in(path):
    return path / ("Scripts/python.exe" if WIN else "bin/python")


def alive(pid):
    if WIN:
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return bool(ok and code.value == 259)
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


def running():
    try:
        value = json.loads((LOCK / "state.json").read_text())
        return value if alive(value["pid"]) else None
    except (OSError, ValueError, KeyError):
        return None


def run(command, cwd=ROOT, env=None):
    subprocess.run([str(x) for x in command], cwd=cwd, env=env, check=True)


def private_env():
    values = {}
    for path in [ROOT / ".env", PRIVATE / ".env"]:
        if path.exists():
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    key, value = line.split("=", 1)
                    values[key.strip()] = value.strip().strip("\"'")
    for key in ["API_TOKEN", "SESSION_SECRET"]:
        if key not in values:
            values[key] = secrets.token_urlsafe(48)
    path = PRIVATE / ".env"
    if not path.exists():
        path.write_text(
            "# Private local configuration. Never share this file.\n"
            + "\n".join(f"{k}={v}" for k, v in values.items())
            + "\n",
            encoding="utf-8",
        )
        path.chmod(0o600)
    return {**values, **os.environ}


def port(preferred=0):
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", preferred))
        except OSError:
            s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def request(url, headers=None, body=None):
    req = urllib.request.Request(url, headers=headers or {}, data=body)
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=3) as r:
        return r.read()


def ready(url, process, headers=None, seconds=90):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        if process.poll() is not None:
            raise RuntimeError("A local service stopped. See data/logs for the error.")
        try:
            request(url, headers)
            return
        except (OSError, urllib.error.URLError):
            time.sleep(0.4)
    raise RuntimeError("The local service did not become ready. See data/logs.")


def source_hash():
    digest = hashlib.sha256()
    paths = [
        ROOT / "package-lock.json",
        ROOT / "apps/web/package.json",
        ROOT / "apps/web/next.config.ts",
        ROOT / "apps/web/postcss.config.mjs",
    ]
    paths += sorted((ROOT / "apps/web/src").rglob("*"))
    for path in paths:
        if path.is_file():
            digest.update(str(path.relative_to(ROOT)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def cleanup():
    for p in reversed(CHILDREN):
        if p.poll() is None:
            if WIN:
                subprocess.run(
                    ["taskkill", "/PID", str(p.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            else:
                try:
                    os.killpg(p.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
    for p in CHILDREN:
        try:
            p.wait(timeout=8)
        except subprocess.TimeoutExpired:
            if not WIN:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
    shutil.rmtree(LOCK, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Add clearly fictional example applications, separate from real jobs",
    )
    parser.add_argument(
        "--repair",
        action="store_true",
        help="Reinstall locked dependencies and rebuild without changing your data",
    )
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        raise RuntimeError(
            "Install Python 3.12 or newer from https://www.python.org/downloads/ and select Add Python to PATH."
        )
    for folder in [DATA, PRIVATE, DATA / "outputs", DATA / "logs"]:
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        folder.chmod(0o700)
    state = running()
    if args.stop:
        if state:
            (LOCK / "stop").touch()
            print("Stop requested. Your records are preserved in data/.")
        else:
            print("CareerPilot is already stopped.")
        return
    if state:
        print("CareerPilot is already running at " + state["url"])
        if not args.no_browser and not args.smoke_test:
            webbrowser.open(state["url"])
        return
    if LOCK.exists():
        # A live launcher may still be writing its state. Never remove its new lock.
        if time.time() - LOCK.stat().st_mtime < 10:
            raise RuntimeError("Another Start window is opening. Wait a moment, or use Stop first.")
        shutil.rmtree(LOCK)
    try:
        LOCK.mkdir(mode=0o700)
    except FileExistsError:
        raise RuntimeError("Another Start window is opening. Use the existing window.") from None
    logs = []
    try:
        env = private_env()
        env.update(
            {
                "CAREERPILOT_DATA_DIR": str(DATA),
                "NEXT_TELEMETRY_DISABLED": "1",
                "UV_LINK_MODE": "copy",
            }
        )
        os.environ.update({k: env[k] for k in ["CAREERPILOT_DATA_DIR", "NEXT_TELEMETRY_DISABLED"]})
        npm = shutil.which("npm.cmd" if WIN else "npm")
        node = shutil.which("node")
        if not npm or not node:
            raise RuntimeError(
                "Install Node.js 24 LTS from https://nodejs.org/ then open Start again."
            )
        version = subprocess.check_output([node, "--version"], text=True).strip().lstrip("v")
        if tuple(int(x) for x in version.split(".")[:2]) < (22, 13):
            raise RuntimeError(
                "Node.js 22.13 or newer is required. Install Node.js 24 LTS from https://nodejs.org/."
            )
        uv = shutil.which("uv")
        uv_cmd = [uv] if uv else [str(python_in(ROOT / ".launcher-venv")), "-m", "uv"]
        if not uv:
            bootstrap = ROOT / ".launcher-venv"
            if not python_in(bootstrap).exists():
                print("Preparing the dependency installer…", flush=True)
                venv.EnvBuilder(with_pip=True).create(bootstrap)
            if subprocess.run(
                uv_cmd + ["--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode:
                run(
                    [python_in(bootstrap), "-m", "pip", "install", "uv==0.12.23"],
                    env=env,
                )
        # Write state before installations, so a second Start cannot duplicate work.
        (LOCK / "state.json").write_text(
            json.dumps({"pid": os.getpid(), "url": "Setup in progress"})
        )
        api_python = python_in(ROOT / "apps/api/.venv")
        lock_hash = hashlib.sha256((ROOT / "apps/api/uv.lock").read_bytes()).hexdigest()
        api_stamp = PRIVATE / "api-dependencies.sha256"
        if (
            args.repair
            or not api_python.exists()
            or not api_stamp.exists()
            or api_stamp.read_text() != lock_hash
        ):
            print("Installing locked Python dependencies…", flush=True)
            run(
                uv_cmd + ["sync", "--frozen", "--no-dev", "--project", "apps/api"],
                env=env,
            )
            api_stamp.write_text(lock_hash)
        npm_hash = hashlib.sha256((ROOT / "package-lock.json").read_bytes()).hexdigest()
        npm_stamp = PRIVATE / "node-dependencies.sha256"
        if (
            args.repair
            or not (ROOT / "node_modules/next").exists()
            or not npm_stamp.exists()
            or npm_stamp.read_text() != npm_hash
        ):
            print("Installing locked browser-app dependencies…", flush=True)
            run([npm, "ci", "--no-audit", "--no-fund"], env=env)
            npm_stamp.write_text(npm_hash)
        print("Preparing your private database…", flush=True)
        run([api_python, "-m", "alembic", "upgrade", "head"], ROOT / "apps/api", env)
        run(
            [api_python, "-m", "careerpilot.initialize"] + (["--demo"] if args.demo else []),
            ROOT / "apps/api",
            env,
        )
        db_file = PRIVATE / "careerpilot.db"
        if db_file.exists():
            db_file.chmod(0o600)
        build_stamp = PRIVATE / "web-build.sha256"
        fingerprint = source_hash()
        if (
            args.repair
            or not (ROOT / "apps/web/.next/BUILD_ID").exists()
            or not build_stamp.exists()
            or build_stamp.read_text() != fingerprint
        ):
            print(
                "Building CareerPilot for your computer. First start takes a few minutes…",
                flush=True,
            )
            run([npm, "run", "build"], env=env)
            build_stamp.write_text(fingerprint)
        api_port, web_port = port(), port(3000)
        while api_port == web_port:
            api_port = port()
        origin = f"http://127.0.0.1:{web_port}"
        code = secrets.token_urlsafe(32)
        env.update(
            {
                "API_BASE_URL": f"http://127.0.0.1:{api_port}",
                "APP_ORIGIN": origin,
                "CAREERPILOT_BOOTSTRAP_CODE": code,
                "CAREERPILOT_BOOTSTRAP_DEADLINE": str(int(time.time() * 1000) + 300000),
            }
        )
        # Backend key and session secret never enter NEXT_PUBLIC variables or browser assets.
        for name, command, cwd in [
            (
                "api",
                [
                    str(api_python),
                    "-m",
                    "uvicorn",
                    "careerpilot.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(api_port),
                    "--no-access-log",
                ],
                ROOT / "apps/api",
            ),
            (
                "web",
                [
                    node,
                    str(ROOT / "node_modules/next/dist/bin/next"),
                    "start",
                    "--hostname",
                    "127.0.0.1",
                    "--port",
                    str(web_port),
                ],
                ROOT / "apps/web",
            ),
        ]:
            handle = open(DATA / "logs" / (name + ".log"), "a", encoding="utf-8")
            os.chmod(handle.name, 0o600)
            logs.append(handle)
            p = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdout=handle,
                stderr=subprocess.STDOUT,
                start_new_session=not WIN,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if WIN else 0,
            )
            CHILDREN.append(p)
        ready(
            env["API_BASE_URL"] + "/api/ready",
            CHILDREN[0],
            {"Authorization": "Bearer " + env["API_TOKEN"]},
        )
        ready(origin, CHILDREN[1])
        (LOCK / "state.json").write_text(json.dumps({"pid": os.getpid(), "url": origin}))
        if args.smoke_test:
            request(
                origin + "/api/unlock",
                {"Origin": origin, "Content-Type": "application/json"},
                json.dumps({"code": code}).encode(),
            )
            print(
                "Smoke test passed: migrated database, production web app, private API and one-use unlock are ready."
            )
            return
        url = origin + "/#code=" + code
        print(
            "\nCareerPilot is ready. Keep this window open.\n"
            + url
            + "\nUse Stop or press Ctrl+C to exit. Your records remain in data/.",
            flush=True,
        )
        if not args.no_browser:
            webbrowser.open(url)
        while not (LOCK / "stop").exists():
            if any(p.poll() is not None for p in CHILDREN):
                raise RuntimeError("A local service stopped. See data/logs.")
            time.sleep(0.5)
    finally:
        cleanup()
        for handle in logs:
            handle.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCareerPilot stopped. Your records are preserved.")
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print("\nCareerPilot could not start: " + str(error), file=sys.stderr)
        print(
            "Your records were preserved. Correct the issue and open Start again.",
            file=sys.stderr,
        )
        sys.exit(1)
