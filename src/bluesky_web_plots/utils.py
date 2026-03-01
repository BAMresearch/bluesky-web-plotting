from event_model import EventDescriptor


def deep_update(original: dict, updates: dict) -> dict:
    """Recursively update a dictionary."""
    for key, value in updates.items():
        if (
            isinstance(value, dict)
            and key in original
            and isinstance(original[key], dict)
        ):
            original[key] = deep_update(original[key], value)
        else:
            original[key] = value
    return original


def hinted_fields(descriptor: EventDescriptor):
    # Figure out which columns to put in the table.
    obj_names = list(descriptor.get("object_keys", []))
    # We will see if these objects hint at whether
    # a subset of their data keys ('fields') are interesting. If they
    # did, we'll use those. If these didn't, we know that the RunEngine
    # *always* records their complete list of fields, so we can use
    # them all unselectively.
    columns = []
    for obj_name in obj_names:
        fields = descriptor.get("hints", {}).get(obj_name, {}).get("fields")
        fields = fields or descriptor.get("object_keys", {}).get(obj_name, [])
        columns.extend(fields)
    return columns
