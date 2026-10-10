## Why Claude Code sends the context again

The model does not remember anything between requests. Thus, Claude Code sends the full context again on every turn. The context includes the system prompt, your project context, and every prior message and tool result. To make this cheaper, Claude Code uses prompt caching.

The unchanged start of the request is the prefix. Claude Code reads the prefix from the cache. A cache read costs only a fraction of the normal input price. On most models, a cache read costs 0.1 times the normal price. On Opus 5.5 and Sonnet 5.5, a cache read costs 0.05 times the normal price. Claude Code fully processes only the newest exchange.

## Cache lifetime

Cached prefixes expire after a period of inactivity. Each request that hits the cache resets the timer. The default lifetime for the main conversation is one hour on a Claude subscription within your plan's usage. With an API key, a cloud provider, or usage credits, the default lifetime is five minutes. If your break is longer than the lifetime, Claude Code must process the full history again as uncached input. In a very long session, this first request is noticeably slower and considerably more expensive.

## Compaction

The conversation grows until it comes near the limit of the context window. Then Claude Code compacts the conversation automatically. Compaction replaces the message history with a summary, the same as a manual `/compact` does. Compaction is cheap while the cache is warm, because the summary request reads the prefix from the cache. Compaction is most expensive after the cache expires. The automatic pass can also start in the middle of a task, and it must guess what is important.

For these reasons, the documentation recommends two actions:

- Compact at natural breaks.
- Run `/clear` between unrelated tasks.

## Automatic handoff

An automatic handoff waits for two conditions: a threshold that you choose, and a natural break. Then the handoff does these steps:

1. It writes a structured summary of the verified results, the failures, and the one next step.
2. It clears the conversation.
3. It continues in a fresh conversation.

With this method, you decide what to keep, not the automatic pass.

## Keeping the cache warm

While you are away, this method sends a tiny request shortly before the cache expires. The request reads the conversation from the cache and resets the timer. When you come back, your next turn is a cache read, not a full reprocessing. But each refresh also costs a cache read of the full conversation. Thus, the method pays off only in long sessions, with breaks not much longer than the cache lifetime.