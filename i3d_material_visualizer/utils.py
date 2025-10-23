from collections import defaultdict
from pathlib import Path

import bpy

from .constants import VEHICLE_SHADER_GROUP_NAME


def import_shader() -> None:
    """Import the vehicleShader node group from the bundled shader.blend file if missing."""
    if VEHICLE_SHADER_GROUP_NAME in bpy.data.node_groups:
        return  # already imported
    library = Path(__file__).parent / "shader.blend"

    try:
        with bpy.data.libraries.load(str(library), link=False) as (data_from, data_to):
            data_to.node_groups = [VEHICLE_SHADER_GROUP_NAME]
    except Exception as e:
        print(f"Failed to import shader from {library}: {e}")


def is_vehicle_shader(material: bpy.types.Material) -> bool:
    """Check if the material is using the vehicleShader."""
    return material.i3d_attributes.shader_name == "vehicleShader"


def get_uv_names_by_index(mat: bpy.types.Material) -> tuple[dict[int, set[str]], list[bpy.types.Object]]:
    """
    Gathers all UV map names for a material's required UV indices across all its user objects.

    Returns a tuple containing:
    - A dictionary mapping the UV index to a set of all found names.
    - A list of all objects using the material.
    """
    if not mat:
        return {}, []
    requirements = mat.i3d_attributes.required_vertex_attributes
    required_indices = [i for i in (1, 2) if f"uv{i}" in requirements]
    if not required_indices:
        return {}, []

    user_objects = [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH" and any(slot.material == mat for slot in obj.material_slots if slot.material)
    ]
    if not user_objects:
        return {}, []

    all_names = defaultdict(set)
    for obj in user_objects:
        for uv_index in required_indices:
            if len(obj.data.uv_layers) > uv_index:
                all_names[uv_index].add(obj.data.uv_layers[uv_index].name)
    return dict(all_names), user_objects


def find_uv_inconsistencies(mat: bpy.types.Material) -> dict[int, set[str]]:
    """Find UV map name inconsistencies for the given material."""
    all_names, _ = get_uv_names_by_index(mat)
    # Filter out indices that have no inconsistencies
    return {index: names for index, names in all_names.items() if len(names) > 1}
