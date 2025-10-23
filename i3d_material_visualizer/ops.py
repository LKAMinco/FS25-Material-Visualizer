from collections import defaultdict

import bpy

from .builder import MaterialVisualizer
from .constants import VEHICLE_SHADER_GROUP_NAME
from .sync import SyncDirection, get_fs_data_path_from_i3dio, sync_param, sync_params, sync_textures
from .utils import find_uv_inconsistencies, is_vehicle_shader


class I3DMaterialVisualizer_OT_sync_shader(bpy.types.Operator):
    bl_idname = "i3d_material_visualizer.sync_shader"
    bl_label = "I3D Material Attributes"
    bl_description = "Sync I3D attributes and the visualizer shader nodes"
    bl_options = {"INTERNAL", "UNDO"}
    bl_property = "direction"

    direction: bpy.props.EnumProperty(
        name="Direction",
        description="Choose how to sync data",
        items=[
            (SyncDirection.PROPS_TO_NODES, "Apply to Shader (Props → Nodes)", "Mat props -> Blender shader nodes"),
            (SyncDirection.NODES_TO_PROPS, "Read from Shader (Nodes → Props)", "Blender shader nodes -> Mat props"),
        ],
        default=SyncDirection.PROPS_TO_NODES,
    )

    single_param: bpy.props.StringProperty(default="", options={"HIDDEN"})
    skip_color_scale: bpy.props.BoolProperty(default=False, options={"HIDDEN"})
    only_color_scale: bpy.props.BoolProperty(default=False, options={"HIDDEN"})

    material: bpy.props.StringProperty(
        name="Material", description="Name of the material to get/set attributes for", default="", options={"HIDDEN"}
    )

    @classmethod
    def description(cls, context, properties):
        tips = "• Shift: Skip colorScale    • Ctrl: Only colorScale\n"
        head = (
            "Props → Nodes (apply to shader)\n"
            if properties.direction == SyncDirection.PROPS_TO_NODES
            else "Nodes → Props (read from shader)\n"
        )
        return head + tips

    @classmethod
    def poll(cls, context):
        return context.material

    def execute(self, context):
        mat = context.material

        if not is_vehicle_shader(mat):
            self.report({"ERROR"}, "Material is not using vehicleShader.")
            return {"CANCELLED"}

        if self.direction == SyncDirection.PROPS_TO_NODES and VEHICLE_SHADER_GROUP_NAME not in mat.node_tree.nodes:
            MaterialVisualizer.enable(mat, self)

        if self.single_param:
            sync_param(mat, self.single_param, self.direction)
            msg = "Applied" if self.direction == SyncDirection.PROPS_TO_NODES else "Read"
            self.report({"INFO"}, f"{msg} {self.single_param!r} on {mat.name!r}.")
            return {"FINISHED"}

        # Bulk parameters
        sync_params(mat, self.direction, skip_color_scale=self.skip_color_scale, only_color_scale=self.only_color_scale)

        # bulk textures
        if not self.only_color_scale:
            sync_textures(mat, self.direction)

        msg = (
            "Applied props/textures to shader"
            if self.direction == SyncDirection.PROPS_TO_NODES
            else "Read shader into props/textures"
        )
        self.report({"INFO"}, f"{msg}: {mat.name!r}.")
        return {"FINISHED"}

    def invoke(self, context, event):
        if not self.single_param:
            self.skip_color_scale = event.shift and not event.ctrl  # If shift is pressed, skip colorScale
            self.only_color_scale = event.ctrl and not event.shift  # If ctrl is pressed, only colorScale
        return self.execute(context)


class I3DMaterialVisualizer_OT_copy_attributes(bpy.types.Operator):
    bl_idname = "i3d_material_visualizer.copy_attributes"
    bl_label = "Copy Material Attributes"
    bl_description = "Copy attributes from source material to destination material"
    bl_options = {"INTERNAL", "UNDO"}

    skip_color_scale: bpy.props.BoolProperty(default=False, options={"HIDDEN"})
    only_color_scale: bpy.props.BoolProperty(default=False, options={"HIDDEN"})

    @classmethod
    def description(cls, context, properties):
        settings = "• Hold Shift: Skip color scale\n• Hold Ctrl: Only apply color scale\n"
        return "Copy attributes from source material to destination material.\n" + settings

    @classmethod
    def poll(cls, context):
        scene_props = context.scene.i3d_material
        if not (scene_props.src_material and scene_props.dst_material and get_fs_data_path_from_i3dio()):
            return False

        return is_vehicle_shader(scene_props.src_material) and is_vehicle_shader(scene_props.dst_material)

    def execute(self, context):
        scene_props = context.scene.i3d_material
        src_material = scene_props.src_material
        dst_material = scene_props.dst_material

        if src_material == dst_material:
            self.report({"ERROR"}, "Source and destination materials cannot be the same.")
            return {"CANCELLED"}

        dst_params = dst_material.i3d_attributes.shader_material_params
        for key, value in src_material.i3d_attributes.shader_material_params.items():
            dst_params[key] = value

        for s, d in zip(
            src_material.i3d_attributes.shader_material_textures, dst_material.i3d_attributes.shader_material_textures
        ):
            d.source = s.source

        MaterialVisualizer.enable(dst_material, self)
        sync_params(
            dst_material,
            SyncDirection.PROPS_TO_NODES,
            skip_color_scale=self.skip_color_scale,
            only_color_scale=self.only_color_scale,
        )
        if not self.only_color_scale:
            sync_textures(dst_material, SyncDirection.PROPS_TO_NODES)

        self.report({"INFO"}, "Material attributes copied successfully.")
        return {"FINISHED"}

    def invoke(self, context, event):
        self.skip_color_scale = event.shift and not event.ctrl  # If shift is pressed, skip colorScale
        self.only_color_scale = event.ctrl and not event.shift  # If ctrl is pressed, only colorScale
        self.execute(context)
        return {"FINISHED"}


class I3DMaterialVisualizer_OT_visualize_all(bpy.types.Operator):
    bl_idname = "i3d_material_visualizer.visualize_all"
    bl_label = "Visualize All Materials"
    bl_description = "Visualize all materials in the scene using I3D Material Visualizer"
    bl_options = {"INTERNAL", "UNDO"}

    enable: bpy.props.BoolProperty(
        name="Enable Visualization",
        description="Enable or disable visualization of all materials",
        default=True,
        options={"HIDDEN"},
    )

    @classmethod
    def poll(cls, context):
        return get_fs_data_path_from_i3dio()

    def execute(self, context):
        for material in bpy.data.materials:
            if material.users == 0:
                continue
            if is_vehicle_shader(material):
                material.i3d_visualized = self.enable
        return {"FINISHED"}


class I3DMaterialVisualizer_OT_standardize_uvs(bpy.types.Operator):
    bl_idname = "i3d_material_visualizer.standardize_uvs"
    bl_label = "Check & Standardize UV Maps"
    bl_description = (
        "Check all vehicleShader materials for inconsistent UV map names and standardize them across all objects"
    )
    bl_options = {"INTERNAL", "UNDO"}

    @classmethod
    def poll(cls, context):
        return get_fs_data_path_from_i3dio()

    def execute(self, context):
        all_inconsistencies = defaultdict(set)
        materials_to_check = [mat for mat in bpy.data.materials if is_vehicle_shader(mat) and mat.users > 0]

        for mat in materials_to_check:
            material_inconsistencies = find_uv_inconsistencies(mat)
            for uv_index, names in material_inconsistencies.items():
                all_inconsistencies[uv_index].update(names)

        if not all_inconsistencies:
            self.report({"INFO"}, "No UV inconsistencies found.")
            return {"FINISHED"}

        master_names = {index: sorted(list(names))[0] for index, names in all_inconsistencies.items()}
        rename_count = 0
        user_objects = [obj for obj in context.scene.objects if obj.type == "MESH"]

        for obj in user_objects:
            for uv_index in all_inconsistencies.keys():
                if len(obj.data.uv_layers) > uv_index:
                    uv_layer = obj.data.uv_layers[uv_index]
                    master_name = master_names[uv_index]

                    # If this layer's name is one of the bad ones and not the chosen master name...
                    if uv_layer.name in all_inconsistencies[uv_index] and uv_layer.name != master_name:
                        uv_layer.name = master_name
                        rename_count += 1

        for mat in materials_to_check:
            if mat.i3d_visualized:
                MaterialVisualizer.enable(mat)

        self.report({"INFO"}, f"Renamed {rename_count} UV maps to standardize names.")
        return {"FINISHED"}


classes = (
    I3DMaterialVisualizer_OT_sync_shader,
    I3DMaterialVisualizer_OT_copy_attributes,
    I3DMaterialVisualizer_OT_visualize_all,
    I3DMaterialVisualizer_OT_standardize_uvs,
)

register, unregister = bpy.utils.register_classes_factory(classes)
