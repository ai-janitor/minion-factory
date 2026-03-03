"""Intel group — add, list, find, get, read, link, suggest, register-docs, for-task, reindex.

Index, link, and query .work/intel/ knowledge docs.
"""

from __future__ import annotations

import click

from minion.cli.main import _output


def register_commands(cli: click.Group) -> None:
    """Attach the intel group and its subcommands to the root CLI."""

    @cli.group("intel")
    @click.pass_context
    def intel_group(ctx: click.Context) -> None:
        """Index, link, and query .work/intel/ knowledge docs."""
        pass

    @intel_group.command("add")
    @click.option("--slug", required=True, help="Human-readable key for this doc")
    @click.option("--path", "doc_path", required=True, help="Absolute path to the .md file")
    @click.option("--tags", default="", help="Comma-separated list of tags")
    @click.option("--description", default="", help="Short description")
    @click.option("--created-by", default="", help="Agent or user who created this doc")
    @click.option("--scaffold", is_flag=True, default=False, help="Create file with frontmatter stub if missing")
    @click.pass_context
    def intel_add(ctx: click.Context, slug: str, doc_path: str, tags: str, description: str, created_by: str, scaffold: bool) -> None:
        """Register an intel doc in the index."""
        from minion.intel import add_doc as _add_doc
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        _output(_add_doc(slug, doc_path, tag_list, description, created_by, scaffold), ctx.obj["human"], ctx.obj["compact"])

    @intel_group.command("link")
    @click.option("--slug", required=True, help="Intel doc slug")
    @click.option("--task", "task_id", type=int, default=None, help="Task ID to link")
    @click.option("--req", "req_id", type=int, default=None, help="Requirement ID to link")
    @click.pass_context
    def intel_link(ctx: click.Context, slug: str, task_id: int | None, req_id: int | None) -> None:
        """Link an intel doc to a task or requirement."""
        from minion.intel import link_doc as _link_doc
        _output(_link_doc(slug, task_id, req_id), ctx.obj["human"], ctx.obj["compact"])

    @intel_group.command("list")
    @click.option("--tag", default="", help="Filter by tag")
    @click.option("--limit", type=int, default=50, help="Max results (default 50)")
    @click.pass_context
    def intel_list(ctx: click.Context, tag: str, limit: int) -> None:
        """List all registered intel docs."""
        from minion.intel import list_docs as _list_docs
        _output(_list_docs(tag, limit), ctx.obj["human"], ctx.obj["compact"])

    @intel_group.command("find")
    @click.option("--tag", default="", help="Filter by tag")
    @click.option("--path", "path_fragment", default="", help="Filter by path fragment")
    @click.pass_context
    def intel_find(ctx: click.Context, tag: str, path_fragment: str) -> None:
        """Find intel docs by tag or path fragment."""
        from minion.intel import find_docs as _find_docs
        _output(_find_docs(tag, path_fragment), ctx.obj["human"], ctx.obj["compact"])

    @intel_group.command("get")
    @click.option("--slug", required=True, help="Intel doc slug")
    @click.pass_context
    def intel_get(ctx: click.Context, slug: str) -> None:
        """Get metadata and links for a registered intel doc."""
        from minion.intel import get_doc as _get_doc
        _output(_get_doc(slug), ctx.obj["human"], ctx.obj["compact"])

    @intel_group.command("read")
    @click.option("--slug", required=True, help="Intel doc slug")
    @click.option("--summary", is_flag=True, default=False, help="Return first 10 lines only")
    @click.pass_context
    def intel_read(ctx: click.Context, slug: str, summary: bool) -> None:
        """Read the content of a registered intel doc."""
        from minion.intel import read_doc as _read_doc
        _output(_read_doc(slug, summary), ctx.obj["human"], ctx.obj["compact"])

    @intel_group.command("for-task")
    @click.option("--task-id", required=True, type=int, help="Task ID to look up intel for")
    @click.pass_context
    def intel_for_task_cmd(ctx: click.Context, task_id: int) -> None:
        """List all intel docs linked to a task."""
        from minion.intel import intel_for_task as _intel_for_task
        _output(_intel_for_task(task_id), ctx.obj["human"], ctx.obj["compact"])

    @intel_group.command("reindex")
    @click.pass_context
    def intel_reindex(ctx: click.Context) -> None:
        """Rebuild intel_docs from filesystem by scanning .work/intel/."""
        from minion.intel import reindex_intel as _reindex_intel
        _output(_reindex_intel(), ctx.obj["human"], ctx.obj["compact"])

    @intel_group.command("suggest")
    @click.option("--topic", default="", help="Topic keywords to search for")
    @click.option("--task-id", default=None, type=int, help="Infer keywords from task title")
    @click.option("--limit", default=5, type=int, help="Max results")
    @click.pass_context
    def intel_suggest(ctx: click.Context, topic: str, task_id: int | None, limit: int) -> None:
        """Suggest relevant intel docs for a topic or task."""
        from minion.intel import suggest as _suggest
        _output(_suggest(topic=topic, task_id=task_id, limit=limit), ctx.obj["human"], ctx.obj["compact"])

    @intel_group.command("register-docs")
    @click.option("--scan-dir", default="docs", help="Directory to scan (default: docs/)")
    @click.option("--created-by", default="register-docs", help="Agent or user registering")
    @click.pass_context
    def intel_register_docs(ctx: click.Context, scan_dir: str, created_by: str) -> None:
        """Bulk-scan a directory and register all .md files in the intel index."""
        from minion.intel import register_docs as _register_docs
        _output(_register_docs(scan_dir=scan_dir, created_by=created_by), ctx.obj["human"], ctx.obj["compact"])
