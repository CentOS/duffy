def camel_case_to_lower_with_underscores(camelcased: str) -> str:
    """Convert CamelCased names to lower_case_with_underscores."""
    chunk_positions = []
    prev_split_pos = 0

    for pos, (prev_is_upper, char_is_upper, next_is_upper) in enumerate(
        zip(
            (x.isupper() for x in camelcased[:-2]),
            (x.isupper() for x in camelcased[1:-1]),
            (x.isupper() for x in camelcased[2:]),
        ),
        start=1,
    ):
        if char_is_upper and (not prev_is_upper or not next_is_upper):
            chunk_positions.append((prev_split_pos, pos))
            prev_split_pos = pos

    chunk_positions.append((prev_split_pos, len(camelcased)))

    lowercased = camelcased.lower()

    return "_".join(
        lowercased[prev_split_pos:split_pos] for prev_split_pos, split_pos in chunk_positions
    )
