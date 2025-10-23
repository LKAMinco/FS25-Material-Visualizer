import bpy

from .builder import MaterialVisualizer
from .constants import VEHICLE_SHADER_GROUP_NAME
from .sync import (
    SyncDirection,
    get_fs_data_path_from_i3dio,
    sync_params,
    sync_textures,
)

MASKS = {
    "Scratches": "show_scratches",
    "Dirt": "show_dirt",
    "Snow": "show_snow",
    "Wetness": "show_wetness",
    "Wetness Mask": "show_wetness_mask",
}


def make_mask_updater(arg: str) -> callable:
    def update_mask(self, context) -> None:
        value = getattr(self, MASKS.get(arg, ""), False)
        for mat in bpy.data.materials:
            if mat.users == 0:
                continue
            if mat.i3d_attributes.shader_name == "vehicleShader":
                if (node := mat.node_tree.nodes.get(VEHICLE_SHADER_GROUP_NAME)) and (sock := node.inputs.get(arg)):
                    sock.default_value = value

    return update_mask


class I3DMaterialVisualizerProperties(bpy.types.PropertyGroup):
    """Scene properties for I3D Material Visualizer"""

    show_wetness_mask: bpy.props.BoolProperty(
        name="Show Wetness Mask",
        description="Show wetness mask in the viewport",
        default=False,
        update=make_mask_updater("Wetness Mask"),
    )

    show_scratches: bpy.props.BoolProperty(
        name="Show Scratches",
        description="Show scratches in the viewport",
        default=False,
        update=make_mask_updater("Scratches"),
    )

    show_dirt: bpy.props.BoolProperty(
        name="Show Dirt",
        description="Show dirt in the viewport",
        default=False,
        update=make_mask_updater("Dirt"),
    )

    show_snow: bpy.props.BoolProperty(
        name="Show Snow",
        description="Show snow in the viewport",
        default=False,
        update=make_mask_updater("Snow"),
    )

    show_wetness: bpy.props.BoolProperty(
        name="Show Wetness",
        description="Show wetness in the viewport",
        default=False,
        update=make_mask_updater("Wetness"),
    )

    src_material: bpy.props.PointerProperty(
        name="Source Material",
        description="Source material for the copy operation",
        type=bpy.types.Material,
    )

    dst_material: bpy.props.PointerProperty(
        name="Destination Material",
        description="Destination material for the copy operation",
        type=bpy.types.Material,
    )


classes = (I3DMaterialVisualizerProperties,)

_register, _unregister = bpy.utils.register_classes_factory(classes)


def update_visualize_material(self, context):
    """Callback for Material.i3d_visualized toggle."""
    if not get_fs_data_path_from_i3dio():
        return

    mat: bpy.types.Material = self.id_data

    if mat.i3d_visualized:
        # Build the node graph if missing
        MaterialVisualizer.enable(mat)
        # Sync all parameters & textures from props to nodes
        sync_params(mat, SyncDirection.PROPS_TO_NODES)
        sync_textures(mat, SyncDirection.PROPS_TO_NODES)
    else:
        # Remove the visualizer nodes and restore pre-existing output
        MaterialVisualizer.disable(mat)


def register():
    _register()
    bpy.types.Scene.i3d_material = bpy.props.PointerProperty(type=I3DMaterialVisualizerProperties)
    bpy.types.Material.i3d_visualized = bpy.props.BoolProperty(
        name="Visualized",
        description="Indicates if the material is being visualized by the I3D Material Visualizer",
        default=False,
        update=update_visualize_material,
    )


def unregister():
    _unregister()
    del bpy.types.Material.i3d_visualized
    del bpy.types.Scene.i3d_material
