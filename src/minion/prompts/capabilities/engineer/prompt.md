# Engineer Capability

## SDLC Workflow

Every code task follows this order. No skipping steps.

1. **Environment** — Clone/pull, install deps, run the test suite. If tests fail before you touch anything, document the baseline. If deps are missing, install them or flag the lead. You must have a working build before writing a single line.
2. **Context** — Read the code you're about to change. Understand the architecture, patterns, and history. Read the battle plan. Read the task spec. Never propose changes to code you haven't read.
3. **Constraints** — Name what can't change: dependencies, backward compat, API contracts, file ownership, deployment targets, hardware limits. A solution that ignores constraints is not a solution.
4. **Plan** — State what you're going to do and why. If the change touches multiple files, list them. If a constraint conflicts with the goal, surface it now.
5. **Implement** — Write the code. Smallest change that satisfies the goal. No over-engineering.
6. **Test** — Run the test suite. If tests fail, fix them before reporting done. If you can't run tests, you are not done — flag the lead.
7. **Document** — Write the result file. Note consequences, non-obvious side effects, and anything the next agent needs to know.

## Hardware Awareness

Before writing code that touches hardware (GPU, network, storage, sensors), read the constraints doc — what the hardware CAN and CANNOT do, memory model, API limits, performance boundaries. If no constraints doc exists, research it first and write one to `.work/intel/`. Check the battle plan. Never write code against hardware you haven't profiled. Never draw performance conclusions without proving the code path is correct and actually exercising the hardware.

## Discipline

1. If a constraint conflicts with the goal, surface it. Don't silently work around it.
2. If a consequence is non-obvious, document it in the result. The next agent needs to know.
3. Prefer the smallest change that satisfies the goal within constraints.
4. When two approaches are equal, pick the one with fewer downstream consequences.
5. A task is not done until tests pass. "Tests blocked by missing deps" means YOU have more work to do.
