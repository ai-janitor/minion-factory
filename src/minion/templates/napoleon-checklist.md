# Napoleon Checklist — <name> [0/N-0NA]

## Mission
- Mission: <mission-title>
- Backlog items: <items>
- Acceptance criteria: <what must pass for mission success>

## Leads
- [ ] Lead <lead-name> — backlog #<ids>
  - [ ] Registered (`minion agent register --name <lead-name> --class lead --model <model-id>`)
  - [ ] Task defined and assigned
  - [ ] Lead checklist verified
  - [ ] Workers spawned and tracked
  - [ ] All workers merged
  - [ ] Tests passing
  - [ ] CLI rebuilt (`uv tool install --force -e .`)
  - [ ] Backlog items closed
  - [ ] Lead deregistered

## Approval Gates
- [ ] All leads reported complete
- [ ] Full test suite passes (`uv run pytest`)
- [ ] CLI rebuilt and verified
- [ ] Backlog fully closed
- [ ] Final sitrep sent to user

## Final
- [ ] All leads deregistered
- [ ] Self deregistered
- [ ] Mission complete
