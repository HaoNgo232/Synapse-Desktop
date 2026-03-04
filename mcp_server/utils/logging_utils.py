"""
Logging Utilities - Cau hinh logging cho MCP server.

Module nay dam bao tat ca log output ghi ra stderr thay vi stdout,
vi MCP stdio transport su dung stdout cho JSON-RPC communication.
"""

import logging
import sys


def force_all_logging_to_stderr() -> None:
    """Ep buoc tat ca logging handlers ghi ra stderr thay vi stdout.

    MCP stdio transport su dung stdout de giao tiep JSON-RPC.
    Bat ky log message nao roi vao stdout se lam hong protocol.

    Quy trinh:
        1. Set MCP flag trong logging_config de bat ky get_logger() call nao
           trong tuong lai (lazy import) cung se dung stderr.
        2. Cau hinh root logger voi stderr handler.
        3. Patch cac Synapse singleton loggers da duoc tao truoc do.
    """
    # 0. Set MCP flag trong logging_config de bat ky get_logger() call nao
    #    trong tuong lai (lazy import) cung se dung stderr thay vi stdout.
    import core.logging_config as _lc

    _lc._MCP_MODE = True

    # Neu logger singleton da duoc tao truoc, reset no de re-create voi stderr
    if _lc._logger is not None:
        _lc._logger = None

    # 1. Cau hinh root logger
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Xoa tat ca handlers cu cua root logger
    for h in root.handlers[:]:
        root.removeHandler(h)

    # Them handler moi ghi ra stderr
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(
        logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
    )
    root.addHandler(stderr_handler)

    # 2. Patch Synapse singleton logger (neu da duoc tao truoc do)
    for name in list(logging.Logger.manager.loggerDict.keys()):
        lg = logging.getLogger(name)
        for h in lg.handlers[:]:
            if (
                isinstance(h, logging.StreamHandler)
                and getattr(h, "stream", None) is sys.stdout
            ):
                lg.removeHandler(h)
                new_h = logging.StreamHandler(sys.stderr)
                new_h.setFormatter(h.formatter)
                new_h.setLevel(h.level)
                lg.addHandler(new_h)

    # NOTE: KHONG thay the sys.stdout o day!
    # MCP StdioServerTransport doc sys.stdout.buffer ben trong mcp.run().
    # Neu ta thay sys.stdout = devnull truoc do, MCP se ghi response vao devnull
    # va AI client se timeout. Handler patching o tren da du de chan log pollution.
