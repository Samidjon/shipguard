"""
Display helpers for the dashboard.

Kept out of the Streamlit module so they can be imported and tested without
starting a Streamlit runtime.
"""


MISSING = "—"


def format_value(value):
    """
    Render a compared field value as display text.

    Everything becomes a string on purpose. The seven compared fields mix
    types — container_count is an int, gross_weight_kg a float, the rest
    strings — and a mixed-type pandas column makes Arrow fail to infer a
    dtype, which produced a traceback on every table render.

    Whole numbers lose the trailing ".0" so a container count of 5 and a
    weight of 100445 read naturally side by side.
    """

    if value is None:
        return MISSING

    if isinstance(value, bool):
        return str(value)

    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    return str(value)
