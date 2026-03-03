"""Comms package — re-exports all public functions.

Consumer imports never change: `from minion.comms import send, check_inbox` still works.
Internals are split by concern across submodules.
"""

from minion.comms.inbox import (
    check_inbox,
    check_inbox_silent,
    get_history,
    purge_inbox,
)
from minion.comms.register import (
    deregister,
    register,
    rename,
    set_context,
    set_status,
    who,
)
from minion.comms.routing import (
    deregister_global,
    prune_global,
    who_global,
)
from minion.comms.send import (
    send,
    send_global,
)

__all__ = [
    "register",
    "deregister",
    "rename",
    "set_status",
    "set_context",
    "who",
    "send",
    "send_global",
    "who_global",
    "deregister_global",
    "prune_global",
    "check_inbox",
    "check_inbox_silent",
    "get_history",
    "purge_inbox",
]
