# Build Capability

1. Look for an existing build process (Makefile, package.json scripts, pyproject.toml build, CI config). Use what exists.
2. If no build process exists, create a Makefile with targets for the project's build steps.
3. If a build process exists but a step is missing (lint, compile, bundle, package, etc.), add a new Makefile target for the missing step — do not modify the existing build tool's config.
4. Every build step must be runnable as `make <target>`. If the underlying tool is npm/uv/cargo/etc., the Makefile target wraps it.
5. `make` with no target should run the default full build.
