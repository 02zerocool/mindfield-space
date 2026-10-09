# Contributing to Mindfield

Thank you for being here. This is a small project with a specific purpose.

## What this project is trying to do

Build the simplest possible skeleton that someone can clone, fill with their own knowledge,
and have a working personal memory field within an hour.

Every contribution should be measured against that goal.

## What helps most

**Documentation**
- Clearer explanations of any step in the quick start
- Translations (the ideas here are not English-specific)
- Better examples of what makes a good personal corpus

**Ingest format support**
- EPUB books
- HTML / web archive
- Obsidian vault format
- Readwise / Kindle highlights export
- Logseq / Roam Research export

**Portability**
- macOS testing and fixes
- ARM / Apple Silicon compatibility
- Docker improvements

**Reports from real use**
What did you put in your corpus? What worked? What surprised you?
These are the most valuable contributions of all.

## What this project is not trying to do

- Be a general-purpose AI platform
- Support multi-user deployments
- Replace any existing AI product
- Abstract over multiple vector databases

If you want to build those things — build them. But not here.

## How to contribute

1. Fork the repo
2. Create a branch: `git checkout -b my-improvement`
3. Make your change
4. Test it: `python scripts/health_check.py`
5. Open a pull request with a clear description of what changed and why

## Code style

- Python: follow PEP 8, no external formatters required
- Keep functions short and readable
- Comment the *why*, not the *what*
- No dependencies that aren't in `requirements.txt`

## A note on the personal nature of this project

The framework is designed to be filled by one person. It is not designed to share corpora,
synchronise memories, or pool knowledge across users.

This is intentional. The value of a personal memory field comes from its specificity.
Contributions that preserve or strengthen this property are welcome.
Contributions that dilute it — by adding shared databases, cloud sync, or multi-user features —
are better pursued as forks.

## Questions

Open a GitHub Discussion. Not an issue — a discussion.
The right venue for "I'm building my corpus from X, does that work?" is a conversation,
not a bug report.
