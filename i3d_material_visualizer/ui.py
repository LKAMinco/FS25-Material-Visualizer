import bpy


class I3D_PT_MaterialVisualizer(bpy.types.Panel):
    bl_label = "I3D Material Visualizer"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_order = 1

    @classmethod
    def poll(cls, context):
        return context.material

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        scene_props = context.scene.i3d_material

        layout.prop(scene_props, "src_material")
        layout.prop(scene_props, "dst_material")
        layout.operator("i3d_material_visualizer.copy_attributes")
        layout.separator(type="LINE")
        layout.operator("i3d_material_visualizer.standardize_uvs")
        row = layout.row(align=True)
        row.operator("i3d_material_visualizer.visualize_all", text="Visualize All Materials").enable = True
        row.operator("i3d_material_visualizer.visualize_all", text="Disable All Materials").enable = False


classes = (I3D_PT_MaterialVisualizer,)

register, unregister = bpy.utils.register_classes_factory(classes)
