"""Mission group — list, suggest, spawn.
Compose a crew from a mission description. AI suggests roles and skills.

Purpose: Mission group — list, suggest, spawn.
Rationale: Extracted into own module for single-responsibility CLI command grouping.
Responsibility: Mission group — list, suggest, spawn. NOT responsible for unrelated concerns.
Organization: Click command group with subcommands."""

from __future__ import annotations

import sys

import click

from minion.cli.main import _output


def register_commands(cli: click.Group) -> None:
    """Attach the mission group and its subcommands to the root CLI."""

    @cli.group("mission")
    @click.pass_context
    def mission_group(ctx: click.Context) -> None:
        """Compose a crew from a mission description. AI suggests roles and skills."""
        pass

    @mission_group.command("list")
    @click.pass_context
    def mission_list(ctx: click.Context) -> None:
        """List available mission templates."""
        from minion.missions import list_missions, load_mission
        names = list_missions()
        missions = []
        for name in names:
            try:
                m = load_mission(name)
                missions.append({"name": m.name, "description": m.description, "requires": m.requires})
            except (ValueError, OSError, KeyError) as exc:
                missions.append({"name": name, "error": f"parse failed: {exc}"})
        _output({"missions": missions}, ctx.obj["human"], ctx.obj["compact"])

    @mission_group.command("suggest")
    @click.argument("mission_type")
    @click.option("--crew", "-c", default="", help="Comma-separated crew names to filter characters")
    @click.option("--project-dir", "-d", default=".", help="Project directory for crew scanning")
    @click.pass_context
    def mission_suggest(ctx: click.Context, mission_type: str, crew: str, project_dir: str) -> None:
        """Show required capabilities, resolved slots, and eligible characters."""
        from minion.missions import load_mission, resolve_slots, suggest_party
        try:
            mission = load_mission(mission_type)
        except FileNotFoundError as e:
            _output({"error": str(e)})
            sys.exit(1)
        slots = resolve_slots(set(mission.requires))
        crews = [c.strip() for c in crew.split(",") if c.strip()] or None
        party = suggest_party(slots, crews=crews, project_dir=project_dir)
        _output({
            "mission": mission.name,
            "description": mission.description,
            "requires": mission.requires,
            "slots": slots,
            "eligible": {slot: chars for slot, chars in party.items()},
        }, ctx.obj["human"], ctx.obj["compact"])

    @mission_group.command("spawn")
    @click.argument("mission_type")
    @click.option("--party", "-p", "party_str", default="", help="Comma-separated character names to spawn")
    @click.option("--crew", "-c", default="", help="Comma-separated crew names to filter characters")
    @click.option("--project-dir", "-d", default=".", help="Project directory")
    @click.option("--runtime", "-r", type=click.Choice(["python", "ts"]), default="python",
                  help="Daemon runtime: python or ts.")
    @click.pass_context
    def mission_spawn(ctx: click.Context, mission_type: str, party_str: str, crew: str, project_dir: str, runtime: str) -> None:
        """Resolve mission slots, suggest party, and spawn."""
        from minion.missions import resolve_and_spawn
        try:
            result = resolve_and_spawn(mission_type, party_str, crew, project_dir, runtime)
        except FileNotFoundError as e:
            _output({"error": str(e)})
            sys.exit(1)
        _output(result, ctx.obj["human"], ctx.obj["compact"])
