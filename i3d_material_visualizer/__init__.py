_needs_reload = "bpy" in locals()

from . import (
    ops,
    props,
    ui,
)

if _needs_reload:
    import importlib

    ops = importlib.reload(ops)
    props = importlib.reload(props)
    ui = importlib.reload(ui)


def register():
    props.register()
    ops.register()
    ui.register()


def unregister():
    ui.unregister()
    ops.unregister()
    props.unregister()
