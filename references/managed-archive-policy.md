# Managed Archive Policy

This policy applies only to the managed archive workflows exposed by this skill:

- `小红书`
- `B站`
- `X`

It does not apply to `书签`, which keeps its existing categories-only structure.

## Canonical Roots

Preserve each source workflow's existing managed roots and naming conventions. The skill entry should not invent a new root layout in v1.

## Cleanup Expectations

For managed archives, preserve these expectations from the existing source workflows:

- cleanup duplicate-suffix folders and files such as `Dashboard 2.md`, `01 日期 2`, or `AI 2`
- migrate legacy English root names into the current canonical roots when the source workflow already supports that behavior
- preserve stable managed roots such as `搜索/Search` and `废弃/Rubbish`

## Rubbish Rules

When the source workflow models upstream removals via a rubbish root:

- move removed items into the existing rubbish root instead of deleting them permanently
- preserve any existing user-kept rubbish content
- avoid visible helper notes in rubbish roots unless the source workflow already expects one

## Publish Rule

The skill entry layer must preserve the current source workflow's publish behavior and output contract. v1 must not rewrite the managed archive engines.
