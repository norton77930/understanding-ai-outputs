# One independent skill per format, no router skill

Each rung of the format ladder is its own skill (`ste-writing`, `diagram-explainer`, `html-explainer`, `video-explainer`) instead of one `explain` skill that picks a format. The formats have very different dependencies (STE needs nothing, video needs animation and TTS tooling), separate skills can be installed and evaluated alone, and a single description covering four triggers would fire unreliably. A user-invoked router (e.g. `/understand`) may be added later on top; it is deliberately out of scope until all four skills are stable.
