"""Pure transform: ThreadStore -> a standalone Markdown thread artifact."""


def export_markdown(store):
    lines = ["# " + (store.title or "marginalia thread"), ""]
    for ev in store.events:
        if ev["type"] == "comment":
            lines.append("> **On:** " + ev["label"])
            lines.append(">")
            lines.append("> \U0001F4AC " + ev["comment"])
            lines.append("")
        else:  # reply
            lines.append("**Reply** _(on: " + ev["label"] + ")_")
            lines.append("")
            lines.append(ev["markdown"])
            lines.append("")
    return "\n".join(lines)
