"""Intel index — queryable knowledge layer over .work/intel/."""

from .add_doc import add_doc
from .list_docs import list_docs
from .find_docs import find_docs
from .get_doc import get_doc
from .read_doc import read_doc
from .link_doc import link_doc
from .for_task import intel_for_task
from .reindex import reindex_intel
from .war_plan import show_war_plan, set_war_plan, append_war_plan

__all__ = [
    "add_doc",
    "list_docs",
    "find_docs",
    "get_doc",
    "read_doc",
    "link_doc",
    "intel_for_task",
    "reindex_intel",
    "show_war_plan",
    "set_war_plan",
    "append_war_plan",
]
