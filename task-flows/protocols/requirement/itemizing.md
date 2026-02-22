# Stage: itemizing

Extracting numbered sections from the raw doc.

## Who acts
Lead or oracle.

## What to do
1. Read the raw `README.md`
2. Extract each discrete requirement into a numbered item
3. Write to `itemized-requirements.md` in the requirement folder
4. Each item = one testable statement OR one investigable question
5. Items should be small enough for one agent in one session to complete
6. If an item is too broad, it will be decomposed further later — don't over-split here

## Format

```markdown
# <Requirement Name>: Itemized Requirements

## <Section heading>

1. **<Short label>** — <one sentence describing what needs to happen or what needs to be understood>

2. **<Short label>** — <one sentence>
```

## How to decide granularity
- Can one agent hold enough context to finish this item? → good size
- Would two agents step on each other's files? → too broad, split
- Is this a single function change? → might be too small, group with related items

## Exit gate
`itemized-requirements.md` exists with numbered items.
