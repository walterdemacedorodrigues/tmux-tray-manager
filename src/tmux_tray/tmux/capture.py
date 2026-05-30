from tmux_tray.tmux.socket import tmux_out

LOG_LINES = 12
LOG_MAX_CHARS = 1200
LOG_REFRESH_MS = 1500


def get_pane_tail(session: str, lines: int = LOG_LINES) -> str:
    """
    Captura últimas N linhas visíveis da pane.
    Usa -J (join wrapped lines) e -S -N para limitar.
    """
    rc, stdout, _, _ = tmux_out(["capture-pane", "-pJ", "-t", session, "-S", f"-{max(1, lines)}"])
    if rc != 0 or not stdout:
        return "(no output)"
    text = stdout.strip()
    if len(text) > LOG_MAX_CHARS:
        text = text[-LOG_MAX_CHARS:]
        nl = text.find("\n")
        if nl != -1:
            text = text[nl + 1:]
    return text
