# Drop your files here

Place `.txt`, `.md`, `.rst`, or `.pdf` files in this directory.

Then run:

```bash
python ingest/ingest_bulk_memory.py --dry-run   # preview
python ingest/ingest_bulk_memory.py --ingest    # write
```

## What makes a good corpus

This is your most important decision. The quality of your memory field is entirely
determined by the quality of what you put in it.

**High signal:**
- Books you've read and found meaningful
- Your own writing — notes, essays, observations
- Research papers in your domain
- Annotated highlights from Readwise / Kindle
- Conversations worth keeping

**Low signal:**
- Wikipedia dumps (too broad, too shallow)
- News articles (ephemeral, low density)
- Code without context
- Anything you haven't actually read

The framework can hold millions of records. But a field of 10,000 deeply personal
records will outperform 1,000,000 generic ones for your purposes every time.

## Tips

- Use descriptive filenames — they become the `source` label in search results
- Split large books into chapters (one file per chapter) for better source attribution
- Personal notes are especially valuable — your own thinking is the point
