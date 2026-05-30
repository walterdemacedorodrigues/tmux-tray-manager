import time
from typing import Dict, Optional

STATE: Dict[str, Dict[str, Optional[str]]] = {}


def get_state(session: str) -> Dict[str, Optional[str]]:
    return STATE.setdefault(session, {"cwd": None, "cmd": None, "ts": time.time()})


def set_state(session: str, cwd: Optional[str], cmd: Optional[str]) -> None:
    st = get_state(session)
    if cwd:
        st["cwd"] = cwd
    if cmd:
        st["cmd"] = cmd
    st["ts"] = time.time()
