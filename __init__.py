import bpy
from bpy.props import StringProperty, BoolProperty, PointerProperty
from bpy.types import (Operator, AddonPreferences, PropertyGroup,
                       Scene, Material)

from .util import update_visualize_material, print, get_param, get_set_params, set_param, update_detail_map, \
    update_mask

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


class I3DMaterial_AddonPreferences(AddonPreferences):
    bl_idname = __package__

    fs25_data_path: StringProperty(
        name="FS 25 Data Path",
        default="",
        subtype='DIR_PATH',
    )

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        split = row.split(factor=0.2)
        split.label(text="FS 25 Data Path")
        split.prop(self, "fs25_data_path", text="")


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
            print(material)
            get_set_params(skip_color_scale=self.skip_color_scale,
                           only_color_scale=self.only_color_scale,
                           mode=self.mode,
                           material=material)
            update_detail_map(context.object.active_material, mode=self.mode)

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


class I3DMaterial_OT_WarningPopup(bpy.types.Operator):
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
            print("Failed to open Addon Preferences for I3D Material Visualizer.")
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
    I3DMaterial_AddonPreferences,
    I3DMaterial_OT_WarningPopup,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
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
    for cls in classes:
        bpy.utils.unregister_class(cls)
