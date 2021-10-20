
def mix(origin: dict, other: dict, keys: list):
    for key in keys:
        if value := other.get(key):
            origin[key] = value


def get_key(dict_: dict, *keys: str):
    for key in keys:
        if value := dict_.get(key):
            return value
