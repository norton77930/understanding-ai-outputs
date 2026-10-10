# claude-code-cache

## s1

The model remembers nothing between requests. So on every turn, Claude Code sends the whole context again: the system prompt, project context, and every prior message and tool result.

## s2

Prompt caching keeps this cheap. The unchanged start, called the prefix, is read from the cache. That costs one tenth of the input price on most models, and one twentieth on Opus and Sonnet five point five.

## s3

The cache expires after inactivity, and each hit resets the timer. On a subscription within your plan, it lasts one hour. With an API key, a cloud provider or usage credits, it lasts five minutes. After a longer break, the whole history is processed again, slower and pricier.

## s4

Near the context limit, Claude Code compacts the history into a summary. This is cheap while the cache is warm, and most expensive after it expires. The automatic pass can run mid-task and must guess what matters. So compact at natural breaks, and clear between unrelated tasks.

## s5

An automatic handoff waits for your threshold and a natural break. It writes a summary of what was verified, what failed, and the one next step. Then it clears the conversation and continues fresh.

## s6

Keeping the cache warm sends a tiny request shortly before expiry. It reads the cache and resets the timer. But each refresh is billed as a cache read of the whole conversation. So it pays off only for long sessions and breaks just past the cache lifetime.
