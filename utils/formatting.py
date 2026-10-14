def format_seconds(seconds: int) -> str:
    """格式化秒数为 `1`h`30`m`10`s 形式"""
    if seconds <= 0:
        return "`0`s"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    time_parts = []
    if hours > 0:
        time_parts.append(f"`{hours}`h")
    if minutes > 0:
        time_parts.append(f"`{minutes}`m")
    if secs > 0 or not time_parts:
        time_parts.append(f"`{secs}`s")

    return "".join(time_parts)
