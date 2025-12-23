import bpy
from bpy_extras.node_shader_utils import PrincipledBSDFWrapper, ShaderImageTextureWrapper

from .graph_utils import apply_presentation, ensure_node, link_sockets, parse_link_path, remove_auto_nodes
from .specs import SPECS, ImageSpec
from .sync import get_fs_data_path_from_i3dio, load_custom_image, set_image
from .utils import get_uv_names_by_index, import_shader


def _adopt_or_create_image_node(texwrap: ShaderImageTextureWrapper) -> bpy.types.Node | None:
    try:
        return texwrap.node_image
    except Exception:
        return None


def adopt_existing_nodes(mat: bpy.types.Material, wrapper: PrincipledBSDFWrapper) -> dict[str, bpy.types.Node]:
    nodes = mat.node_tree.nodes
    adopted: dict[str, bpy.types.Node] = {}

    if base_img_node := _adopt_or_create_image_node(wrapper.base_color_texture):
        adopted["Diffuse"] = base_img_node
        base_img_node["i3d_role"] = "Diffuse"
    if normalmap := wrapper.node_normalmap:
        adopted["Normal Map"] = normalmap
        normalmap["i3d_role"] = "Normal Map"
    if normalmap_img_node := _adopt_or_create_image_node(wrapper.normalmap_texture):
        adopted["Normal"] = normalmap_img_node
        normalmap_img_node["i3d_role"] = "Normal"
    if gloss := nodes.get("Glossmap"):
        if gloss.bl_idname == "ShaderNodeSeparateColor":
            adopted["Glossmap"] = gloss
            gloss["i3d_role"] = "Glossmap"
            if (
                gloss.inputs.get("Color").is_linked
                and gloss.inputs["Color"].links[0].from_node.bl_idname == "ShaderNodeTexImage"
            ):
                spec_tex = gloss.inputs["Color"].links[0].from_node
                adopted["Specular"] = spec_tex
                spec_tex["i3d_role"] = "Specular"
        elif gloss.bl_idname == "ShaderNodeTexImage":
            adopted["Specular"] = gloss
            gloss["i3d_role"] = "Specular"
    elif spec_tex_node := _adopt_or_create_image_node(wrapper.specular_texture):
        adopted["Specular"] = spec_tex_node
        spec_tex_node["i3d_role"] = "Specular"
    return adopted


def _assign_image(mat: bpy.types.Material, node: bpy.types.Node, image_spec: ImageSpec) -> None:
    if node.bl_idname != "ShaderNodeTexImage" or not image_spec:
        return
    textures = mat.i3d_attributes.shader_material_textures
    if image_spec.key and image_spec.key in textures:
        slot = textures[image_spec.key]
        path = slot.source or slot.default_source
        if path:
            img = load_custom_image(path)
            set_image(img, node, image_spec.colorspace)
            return
    if not getattr(node, "image") and image_spec.default:
        img = load_custom_image(image_spec.default)
        set_image(img, node, image_spec.colorspace)


class Report:
    def __init__(self, operator: bpy.types.Operator | None = None):
        self.operator = operator
        self.warnings: list[str] = []

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)
        if self.operator:
            self.operator.report({"WARNING"}, msg)
        else:
            print(f"MaterialVisualizer: WARNING: {msg}")


class MaterialVisualizer:
    def __init__(self, mat: bpy.types.Material, operator: bpy.types.Operator | None = None):
        self.mat = mat
        self.nodes: dict[str, bpy.types.Node] = {}
        self.wrapper = PrincipledBSDFWrapper(mat, is_readonly=False)
        self.reporter = Report(operator)

    def _ensure_principled_bridge(self):
        return bool(self.wrapper.node_out)

    def _ensure_shader_group(self):
        import_shader()

    def _configure_uv_nodes(self):
        all_uv_names, user_objects = get_uv_names_by_index(self.mat)
        if not user_objects:
            return

        def assign_uv_map_for_node(uv_index: int, node_role: str):
            node = self.nodes.get(node_role)
            if not node:
                return
            names_found = all_uv_names.get(uv_index)
            for obj in user_objects:
                if len(obj.data.uv_layers) <= uv_index:
                    self.reporter.warn(
                        f"{obj.name!r} is missing UV map at index {uv_index} required by material {self.mat.name!r}."
                    )
                    # Can't proceed reliably if a layer is missing on any object
                    return
                if not names_found:
                    return  # Should be covered above, but just in case

                if len(names_found) > 1:
                    self.reporter.warn(
                        f"Inconsistent UV map names at index {uv_index} for material "
                        f"{self.mat.name!r}. Found: {list(names_found)}. Using one as a fallback."
                    )
                    # Using sorted list to make the fallback choice deterministic
                    chosen_name = sorted(list(names_found))[0]
                else:  # Success, found a single consistent name
                    chosen_name = names_found.pop()

                if chosen_name:
                    node.uv_map = chosen_name

        requirements = self.mat.i3d_attributes.required_vertex_attributes
        if "uv1" in requirements:
            assign_uv_map_for_node(1, "uv_spec")
        if "uv2" in requirements:
            assign_uv_map_for_node(2, "uv_norm")

    def _position_nodes(self):
        occupied_locations = set()
        for role, spec in SPECS.items():
            node_to_place = self.nodes.get(role)
            if not node_to_place or not spec.location:
                continue
            final_location = (0, 0)
            if spec.location_relative_to and (anchor := self.nodes.get(spec.location_relative_to)):
                final_location = (anchor.location.x + spec.location[0], anchor.location.y + spec.location[1])
            else:
                final_location = spec.location

            while final_location in occupied_locations:
                final_location = (final_location[0], final_location[1] - 40)  # shift down to avoid overlap
            node_to_place.location = final_location
            occupied_locations.add(final_location)

    def apply(self):
        if not get_fs_data_path_from_i3dio():
            return
        self._ensure_shader_group()
        if not self._ensure_principled_bridge():
            return
        adopted = adopt_existing_nodes(self.mat, self.wrapper)
        # build nodes
        for role, spec in SPECS.items():
            if spec.only_if_adopted and role not in adopted:
                continue
            self.nodes[role] = adopted.get(role) or ensure_node(self.mat, spec)

        self._position_nodes()

        glossmap_is_present = self.nodes.get("Glossmap") is not None

        for role, spec in SPECS.items():
            this_node = self.nodes.get(role)
            if not this_node:
                continue

            # Determine link directions and process conditions
            all_links_with_direction = [(link, True) for link in spec.from_node] + [
                (link, False) for link in spec.to_node
            ]

            for link, is_from_node_link in all_links_with_direction:
                if link.condition == "glossmap_exists" and not glossmap_is_present:
                    continue
                if link.condition == "glossmap_missing" and glossmap_is_present:
                    continue

                # Parse the link path and link sockets
                if parts := parse_link_path(link.path):
                    this_sock, other_node_role, other_sock = parts
                    other_node = self.nodes.get(other_node_role)
                    if other_node:
                        link_sockets(this_node, other_node, this_sock, other_sock, from_node=is_from_node_link)

        self._configure_uv_nodes()

        for role, spec in SPECS.items():
            if not (node := self.nodes.get(role)):
                continue
            _assign_image(self.mat, node, spec.image)
            apply_presentation(node, spec)

    @staticmethod
    def enable(mat: bpy.types.Material) -> None:
        MaterialVisualizer(mat).apply()

    @staticmethod
    def disable(mat: bpy.types.Material) -> None:
        remove_auto_nodes(mat)
        # Ensure the output and BSDF still exist and set active output
        wrapper = PrincipledBSDFWrapper(mat, is_readonly=False)
        if wrapper.node_out:
            wrapper.node_out.is_active_output = True
