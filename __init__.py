import bpy
from bpy.props import BoolProperty, PointerProperty
from bpy.types import (Operator, Panel, PropertyGroup, Scene, Material)

from .util import (
    update_visualize_material, log_warning, get_param, get_set_params, set_param, update_detail_map, update_mask,
    get_fs_data_path_from_i3dio
)

bl_info = {
    "name": "I3D Material Visualizer",
    "author": "LKAMinco",
    "description": "Tool for visualizing Farming Simulator 25 materials",
    "blender": (4, 5, 0),
    "version": (1, 0, 0),
    "location": "View3D",
    "warning": "",
    "category": "3D View",
}


class I3DMaterial_OperatorGetSet(Operator):
    """Operator to get or set I3D material attributes"""
    bl_idname = "i3d_material_visualizer.get_set"
    bl_label = "I3D Material Attributes"
    bl_options = {'REGISTER', 'UNDO'}
    bl_property = "mode"

    mode: bpy.props.EnumProperty(
        name="Mode",
        description="Choose to get or set I3D material attributes",
        items=[
            ('GET', "Get Attributes", ""),
            ('SET', "Set Attributes", "")
        ],
        default='GET'
    )
    single_param: bpy.props.StringProperty(default="", options={'HIDDEN'})
    skip_color_scale: bpy.props.BoolProperty(default=False, options={'HIDDEN'})
    only_color_scale: bpy.props.BoolProperty(default=False, options={'HIDDEN'})

    material: bpy.props.StringProperty(
        name="Material",
        description="Name of the material to get/set attributes for",
        default="",
        options={'HIDDEN'}
    )

    @classmethod
    def description(cls, context, properties):
        settings = ("• Hold Shift: Skip color scale\n"
                    "• Hold Ctrl: Only apply color scale\n")
        if properties.single_param:
            settings = f"• Single Parameter: {properties.single_param}\n"
        if properties.mode == 'GET':
            return "Giants Shader -> Blender Shader.\n" + settings
        elif properties.mode == 'SET':
            return "Blender Shader -> Giants Shader.\n" + settings
        return "Unknown mode"

    @classmethod
    def poll(cls, context):
        if 'i3dio' not in bpy.context.preferences.addons:
            return False
        return (context.object
                and context.object.active_material
                and context.object.active_material.i3d_visualized
                and hasattr(context.object.active_material, 'i3d_attributes')
                and context.object.active_material.i3d_attributes.shader_name == 'vehicleShader')

    def execute(self, context):
        if self.material == "":
            material = context.object.active_material
        else:
            material = bpy.data.materials.get(self.material)
            if not material:
                self.report({'ERROR'}, f"Material '{self.material}' not found.")
                return {'CANCELLED'}

        if self.single_param:
            get_param(self.single_param, material) if self.mode == 'GET' else set_param(self.single_param, material)
        else:
            get_set_params(material, skip_color_scale=self.skip_color_scale,
                           only_color_scale=self.only_color_scale,
                           mode=self.mode)
            if not self.only_color_scale:
                update_detail_map(material, mode=self.mode)

        return {'FINISHED'}

    def invoke(self, context, event):
        if not self.single_param:
            self.skip_color_scale = event.shift and not event.ctrl  # If shift is pressed, skip colorScale
            self.only_color_scale = event.ctrl and not event.shift  # If ctrl is pressed, only colorScale
        self.execute(context)
        return {'FINISHED'}


class I3DMaterial_SceneProperties(PropertyGroup):
    """Scene properties for I3D Material Visualizer"""
    show_wetness_mask: BoolProperty(
        name="Show Wetness Mask",
        description="Show wetness mask in the viewport",
        default=False,
        update=update_mask('Wetness Mask')
    )

    show_scratches: BoolProperty(
        name="Show Scratches",
        description="Show scratches in the viewport",
        default=False,
        update=update_mask('Scratches')
    )

    show_dirt: BoolProperty(
        name="Show Dirt",
        description="Show dirt in the viewport",
        default=False,
        update=update_mask('Dirt')
    )

    show_snow: BoolProperty(
        name="Show Snow",
        description="Show snow in the viewport",
        default=False,
        update=update_mask('Snow')
    )

    show_wetness: BoolProperty(
        name="Show Wetness",
        description="Show wetness in the viewport",
        default=False,
        update=update_mask('Wetness')
    )

    src_material: PointerProperty(
        name="Source Material",
        description="Source material for the copy operation",
        type=Material
    )

    dst_material: PointerProperty(
        name="Destination Material",
        description="Destination material for the copy operation",
        type=Material
    )


class I3DMaterial_PT_Panel(Panel):
    bl_label = "I3D Material Visualizer"
    bl_idname = "I3D_MATERIAL_PT_panel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    bl_category = "I3D Material"

    def draw(self, context):
        layout = self.layout
        scene_props = context.scene.i3d_material

        layout.prop(scene_props, "src_material", text="Src Mat")
        layout.prop(scene_props, "dst_material", text="Dst Mat")
        layout.operator("i3d_material_visualizer.copy_attributes", text="Copy Attributes")
        layout.separator()
        row = layout.row(align=True)
        row.operator("i3d_material_visualizer.visualize_all", text="Visualize All Materials").enable = True
        row.operator("i3d_material_visualizer.visualize_all", text="Disable All Materials").enable = False
        layout.separator()


class I3DMaterial_OT_CopyAttributes(Operator):
    bl_idname = "i3d_material_visualizer.copy_attributes"
    bl_label = "Copy Material Attributes"
    bl_description = "Copy attributes from source material to destination material"
    bl_options = {'REGISTER', 'UNDO'}

    skip_color_scale: bpy.props.BoolProperty(default=False, options={'HIDDEN'})
    only_color_scale: bpy.props.BoolProperty(default=False, options={'HIDDEN'})

    @classmethod
    def description(cls, context, properties):
        settings = ("• Hold Shift: Skip color scale\n"
                    "• Hold Ctrl: Only apply color scale\n")
        return "Copy attributes from source material to destination material.\n" + settings

    @classmethod
    def poll(cls, context):
        scene_props = context.scene.i3d_material
        if not (scene_props.src_material
                and scene_props.dst_material
                and get_fs_data_path_from_i3dio()):
            return False

        return scene_props.dst_material.node_tree.nodes.get(
            'FS25_VehicleShader') and scene_props.src_material.node_tree.nodes.get('FS25_VehicleShader')

    def execute(self, context):
        scene_props = context.scene.i3d_material
        src_material = scene_props.src_material
        dst_material = scene_props.dst_material

        if src_material == dst_material:
            self.report({'ERROR'}, "Source and destination materials cannot be the same.")
            return {'CANCELLED'}

        for key, val in src_material.i3d_attributes.shader_material_params.items():
            dst_material.i3d_attributes.shader_material_params[key] = val

        for idx, param in enumerate(src_material.i3d_attributes.shader_material_textures):
            dst_material.i3d_attributes.shader_material_textures[idx].source = param.source

        bpy.ops.i3d_material_visualizer.get_set(
            'INVOKE_DEFAULT',
            mode='GET',
            material=dst_material.name,
            skip_color_scale=self.skip_color_scale,
            only_color_scale=self.only_color_scale
        )

        self.report({'INFO'}, "Material attributes copied successfully.")
        return {'FINISHED'}

    def invoke(self, context, event):
        self.skip_color_scale = event.shift and not event.ctrl  # If shift is pressed, skip colorScale
        self.only_color_scale = event.ctrl and not event.shift  # If ctrl is pressed, only colorScale
        self.execute(context)
        return {'FINISHED'}


class I3DMaterial_OT_VisualizeAll(Operator):
    bl_idname = "i3d_material_visualizer.visualize_all"
    bl_label = "Visualize All Materials"
    bl_description = "Visualize all materials in the scene using I3D Material Visualizer"
    bl_options = {'REGISTER', 'UNDO'}

    enable: BoolProperty(
        name="Enable Visualization",
        description="Enable or disable visualization of all materials",
        default=True,
        options={'HIDDEN'}
    )

    @classmethod
    def poll(cls, context):
        return get_fs_data_path_from_i3dio()

    def execute(self, context):
        for material in bpy.data.materials:
            if material.i3d_attributes.shader_name != 'vehicleShader':
                continue
            material.i3d_visualized = self.enable
        return {'FINISHED'}


class I3DMaterial_OT_WarningPopup(Operator):
    bl_idname = "i3d_material_visualizer.warning_popup"
    bl_label = "Warning"
    bl_options = {'INTERNAL'}

    message: bpy.props.StringProperty()

    def execute(self, context):
        try:
            bpy.ops.screen.userpref_show('INVOKE_DEFAULT')
        except Exception:
            pass
        try:
            bpy.ops.preferences.addon_show(module=__name__.split(".", 1)[0])
        except Exception:
            self.report({'ERROR'},
                        "Failed to open Addon Preferences. Please check your Blender version and addon installation.")
            log_warning("Failed to open Addon Preferences for I3D Material Visualizer.")
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        layout.label(text=self.message)
        layout.label(text="Please set the FS 25 Data Path in the Addon Preferences.")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)


classes = (
    I3DMaterial_SceneProperties,
    I3DMaterial_OperatorGetSet,
    I3DMaterial_PT_Panel,
    I3DMaterial_OT_CopyAttributes,
    I3DMaterial_OT_VisualizeAll,
    I3DMaterial_OT_WarningPopup,
)
_register, _unregister = bpy.utils.register_classes_factory(classes)


def register():
    _register()
    Material.i3d_visualized = BoolProperty(
        name="Visualized",
        description="Indicates if the material is being visualized by the I3D Material Visualizer",
        default=False,
        update=update_visualize_material
    )
    Scene.i3d_material = PointerProperty(type=I3DMaterial_SceneProperties)


def unregister():
    del Material.i3d_visualized
    del Scene.i3d_material
    _unregister()
