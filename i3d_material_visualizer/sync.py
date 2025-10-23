from enum import Enum
from pathlib import Path

import bpy

from .constants import I3DIO_ADDON_ID, VEHICLE_SHADER_GROUP_NAME
from .specs import SPECS


class SyncDirection(str, Enum):
    PROPS_TO_NODES = "PROPS_TO_NODES"  # Material props -> Blender Shader nodes
    NODES_TO_PROPS = "NODES_TO_PROPS"  # Blender Shader nodes -> Material props


ATTR_MAP: dict[str, tuple[str, str]] = {
    "colorScale": ("colorScale", "Color"),
    "smoothnessScale": ("smoothnessScale", "Smoothness Scale"),
    "metalnessScale": ("metalnessScale", "Metalness Scale"),
    "clearCoatIntensity": ("clearCoatIntensity", "Clear Coat Intensity"),
    "clearCoatSmoothness": ("clearCoatSmoothness", "Clear Coat Smoothness"),
    "porosity": ("porosity", "Porosity"),
}


def check_i3dio_enabled() -> bool:
    return any(a.module.endswith(I3DIO_ADDON_ID) for a in bpy.context.preferences.addons.values())


def get_fs_data_path_from_i3dio() -> str | None:
    addon = next((a for a in bpy.context.preferences.addons.values() if a.module.endswith(I3DIO_ADDON_ID)), None)
    return addon.preferences.fs_data_path if addon else None


def get_file_from_data(file_path):
    s = str(file_path)
    if s.startswith("$data"):
        return Path(get_fs_data_path_from_i3dio()) / s[6:]
    return Path(s)


def get_data_path_from_file(file_path: str | Path) -> str | None:
    """Convert absolute file path to $data relative path, if inside the FS data directory."""
    fs_data_path = get_fs_data_path_from_i3dio()
    if not fs_data_path:
        return None
    fs_data_path = Path(fs_data_path)
    file_path = Path(bpy.path.abspath(str(file_path)))
    try:
        relative = file_path.relative_to(fs_data_path)
    except ValueError:
        return None
    return f"$data/{relative.as_posix()}"


def is_same_asset(path1: str, path2: str) -> bool:
    """Check if two file paths point to the same asset in the FS data directory."""
    pa1, pa2 = Path(path1), Path(path2)
    return pa1.parent.as_posix().lower() == pa2.parent.as_posix().lower() and pa1.stem.lower() == pa2.stem.lower()


def load_custom_image(image_path: str) -> bpy.types.Image | None:
    if image_path == "":
        return None
    image = bpy.data.images.get(str(Path(image_path).name))
    if image is None:
        image = bpy.data.images.get(str(Path(image_path).with_suffix(".dds").name))
    if image is None:
        fs_image_path = get_file_from_data(image_path)
        if not fs_image_path.exists():
            fs_image_path = image_path.replace(".png", ".dds")
        image = bpy.data.images.load(str(get_file_from_data(fs_image_path)))
    return image


def set_image(image: bpy.types.Image | None, image_node, color_space="Color"):
    try:
        image_node.image = image

        if color_space == "Non-Color" and image_node.image:
            image_node.image.colorspace_settings.name = "Non-Color"

    except RuntimeError:
        print(f"I3D_Material_Visualizer: Could not load image for node {getattr(image_node, 'name', '?')}")


# --------------------------------------------------------------------------------------
# Spec-driven syncing API (values + textures) used by operators and builder if needed
# --------------------------------------------------------------------------------------


def _get_vehicle_shader_node(material: bpy.types.Material) -> bpy.types.Node | None:
    nt = getattr(material, "node_tree", None)
    return None if not nt else nt.nodes.get(VEHICLE_SHADER_GROUP_NAME)


def sync_param(material: bpy.types.Material, param: str, direction: SyncDirection) -> None:
    i3d_params = material.i3d_attributes.shader_material_params
    vehicle_shader_node = _get_vehicle_shader_node(material)
    info = ATTR_MAP.get(param)
    if not info or vehicle_shader_node is None:
        return
    prop_key, socket_name = info
    if prop_key not in i3d_params:
        return

    socket = vehicle_shader_node.inputs.get(socket_name)
    if socket is None:
        return

    if prop_key == "colorScale":
        if direction == SyncDirection.PROPS_TO_NODES:
            socket.default_value = i3d_params[prop_key][0:3] + (1.0,)
        else:
            material.i3d_attributes.shader_material_params[prop_key] = socket.default_value[0:3]
        return

    if direction == SyncDirection.PROPS_TO_NODES:
        socket.default_value = i3d_params[prop_key][0]
    else:
        i3d_params[prop_key][0] = socket.default_value


def sync_params(
    material: bpy.types.Material,
    direction: SyncDirection,
    *,
    skip_color_scale: bool = False,
    only_color_scale: bool = False,
) -> None:
    if only_color_scale:
        sync_param(material, "colorScale", direction)
        return
    for param in ATTR_MAP.keys():
        if skip_color_scale and param == "colorScale":
            continue
        sync_param(material, param, direction)


def sync_textures(material: bpy.types.Material, direction: SyncDirection) -> None:
    """
    Texture sync based on SPECS:
      - PROPS_TO_NODES: copy slot -> node.image (apply colorspace)
      - NODES_TO_PROPS: copy node.image path -> slot.source (as $data when possible)
    Only NodeSpecs with `image` and TexImage nodes are considered.
    """
    nt = getattr(material, "node_tree", None)
    if not nt:
        return

    slots = material.i3d_attributes.shader_material_textures

    for role, spec in SPECS.items():
        img_spec = spec.image
        if not img_spec:
            continue
        node = nt.nodes.get(role)
        if not node or node.bl_idname != "ShaderNodeTexImage":
            continue

        key = img_spec.key
        if not key or key not in slots:
            # default-only image role, only applies PROPS_TO_NODES
            if direction == SyncDirection.PROPS_TO_NODES and img_spec.default and getattr(node, "image", None) is None:
                img = load_custom_image(img_spec.default)
                set_image(img, node, img_spec.colorspace)
            continue

        # Slot exists by RNA contract
        slot = slots[key]

        if direction == SyncDirection.PROPS_TO_NODES:
            src = slot.source or slot.default_source
            if not src:
                continue
            img = load_custom_image(src)
            set_image(img, node, img_spec.colorspace)

        else:  # NODES_TO_PROPS
            path = node.image.filepath if getattr(node, "image", None) else ""
            if not path:
                slot.source = ""
                continue
            data_path = get_data_path_from_file(path) or path
            # avoid re-storing same-as-default
            slot.source = "" if is_same_asset(data_path, slot.default_source) else data_path
