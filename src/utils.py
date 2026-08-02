def biased_sort(items: list[str], priority: list[str]) -> list[str]:
    priority_items = [s for s in priority if s in items]
    rest = sorted((s for s in items if s not in priority), key=lambda s: (s[0].isdigit(), s))
    return priority_items + rest 

