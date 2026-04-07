# Taxonomy Policy

This plugin owns the shared taxonomy policy layer for all plugin-local archive entry skills.

## Precedence

When a source workflow needs a taxonomy or classification reference, use this order:

1. An explicit taxonomy or rules path provided by the user or required by the source workflow
2. A local archive `ROOT分类目录.md` already present in the target archive
3. The source workflow's built-in default taxonomy fallback

## AI_OUTLINE_V1

If the selected Markdown taxonomy contains `FORMAT: AI_OUTLINE_V1`, treat it as the canonical taxonomy tree:

- classify content semantically into that tree
- preserve the tree as the source of truth on merge/update flows
- do not let incoming exports silently replace the established taxonomy

## Merge Behavior

For merge or update flows:

- inspect the existing archive first when the source workflow supports it
- preserve the archive's current taxonomy unless the user explicitly asks to rewrite or reclassify it
- prefer placing new items into the established taxonomy rather than inventing a parallel structure

## Scope Notes

- `书签库` shares taxonomy policy only; it keeps its own categories-only archive shape
- `小红书`, `B站`, and `X Likes` use this policy for their domain taxonomy decisions inside their existing managed archive structures
