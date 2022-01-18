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


def merge_dicts(*src_dicts):
    """Create a deep merge of several dictionaries.

    The structure of the dictionaries must be compatible, i.e. sub-dicts
    may not be differently typed between the source dictionaries."""
    if not src_dicts:
        raise ValueError("Can't merge nothing")

    if not all(isinstance(src_dict, dict) for src_dict in src_dicts):
        raise TypeError("All objects to be merged have to be dictionaries")

    res_dict = {}

    for src_dict in src_dicts:
        for key, src_value in src_dict.items():
            if isinstance(src_value, dict):
                if key not in res_dict:
                    res_dict[key] = src_value.copy()
                else:
                    res_dict[key] = merge_dicts(res_dict[key], src_value)
            elif key in res_dict and isinstance(res_dict[key], dict):
                raise TypeError("All objects to be merged have to be dictionaries")
            else:
                res_dict[key] = src_value

    return res_dict
