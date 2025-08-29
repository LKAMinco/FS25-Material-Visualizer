import logging
import bpy
from pathlib import Path


ROLE_PROP = "i3d_role"
I3DIO_ADDON_ID = "i3dio"


ATTR_MAP: dict[str, tuple[str, str]] = {
    'colorScale': ('colorScale', 'Color'),
    'smoothnessScale': ('smoothnessScale', 'Smoothness Scale'),
    'metalnessScale': ('metalnessScale', 'Metalness Scale'),
    'clearCoatIntensity': ('clearCoatIntensity', 'Clear Coat Intensity'),
    'clearCoatSmoothness': ('clearCoatSmoothness', 'Clear Coat Smoothness'),
    'porosity': ('porosity', 'Porosity'),
}

NODE_SETTINGS: dict[str, dict[str, str | tuple[int, int]]] = {
    'Principled BSDF': {
        'location': (180, 420),
        'bl_idname': 'ShaderNodeBsdfPrincipled',
        'from_node': ('Normal.Normal Map.Normal', 'Base Color.Diffuse.Color',),
        'hide_unused': True,
    },
    'Material Output': {
        'location': (480, 300),
        'bl_idname': 'ShaderNodeOutputMaterial',
        'from_node': ('Surface.FS25_VehicleShader.BSDF',),
    },
    'FS25_VehicleShader': {
        'location': (180, 240),
        'bl_idname': 'ShaderNodeGroup',
        'group': 'FS25_VehicleShader',
        'to_node': ('BSDF.Material Output.Surface',),
        'from_node': (
            'Detail Diffuse.Detail Diffuse.Color',
            'Detail Specular.Detail Specular.Color',
            'Detail Normal.Detail Normal.Color',
            'Vector.detail_mapping.Generated UV',
            'uv0.uv_diff.UV',
            'uv1.uv_spec.UV',
            'uv2.uv_norm.UV',
        ),
        'hide_unused': True,
    },
    'Glossmap': {
        'location': (-60, 360),
        'bl_idname': 'ShaderNodeSeparateColor',
        'from_node': ('Color.Specular.Color',),
        'collapsed': True,
    },
    'Diffuse': {
        'location': (-500, 380),
        'bl_idname': 'ShaderNodeTexImage',
        'to_node': (
            'Color.Principled BSDF.Base Color', 'Color.FS25_VehicleShader.Diffuse', 'Alpha.FS25_VehicleShader.Alpha',
        ),
        'from_node': ('Vector.uv_diff.UV',),
        'colorspace': 'Color',
        'default_image': '$data/shared/white_diffuse.dds',
    },
    'Specular': {
        'location': (-500, 340),
        'bl_idname': 'ShaderNodeTexImage',
        'to_node': ('Color.Glossmap.Color', 'Color.FS25_VehicleShader.Specular',),
        'from_node': ('Vector.uv_spec.UV',),
        'colorspace': 'Non-Color',
        'default_image': '$data/shared/default_vmask.dds',
    },
    'Normal Map': {
        'location': (-60, 320),
        'bl_idname': 'ShaderNodeNormalMap',
        'to_node': ('Normal.Principled BSDF.Normal',),
        'from_node': ('Color.Normal.Color',),
        'collapsed': True,
    },
    'Normal': {
        'location': (-500, 300),
        'bl_idname': 'ShaderNodeTexImage',
        'to_node': ('Color.Normal Map.Color', 'Color.FS25_VehicleShader.Normal'),
        'from_node': ('Vector.uv_norm.UV',),
        'colorspace': 'Non-Color',
        'default_image': '$data/shared/default_normal.dds',
    },
    'Lights Intensity': {
        'location': (-500, 140),
        'bl_idname': 'ShaderNodeTexImage',
        'to_node': ('Color.FS25_VehicleShader.Lights Intensity',),
        'from_node': ('Vector.uv_spec.UV',),
        'image_key': 'lightsIntensity',  # optional slot
        'colorspace': 'Color',
        'optional': True,  # don’t warn if missing
        'collapsed': True,
        'hide_unused': True,
    },

    # Keep separate uv nodes per "base" texture, since specular and normal maps technically can use different UVs
    'uv_diff': {
        'location': (-700, 380),
        'bl_idname': 'ShaderNodeUVMap',
        'to_node': ('UV.Diffuse.Vector',),
        'collapsed': True,
    },
    'uv_spec': {
        'location': (-700, 340),
        'bl_idname': 'ShaderNodeUVMap',
        'to_node': ('UV.Specular.Vector', 'UV.Lights Intensity.Vector',),
        'collapsed': True,
    },
    'uv_norm': {
        'location': (-700, 300),
        'bl_idname': 'ShaderNodeUVMap',
        'to_node': ('UV.Normal.Vector',),
        'collapsed': True,
    },
    'texcoord': {
        'location': (-860, -60),
        'bl_idname': 'ShaderNodeTexCoord',
        'hide_unused': True,
    },
    'detail_mapping': {
        'location': (-700, -60),
        'bl_idname': 'ShaderNodeMapping',
        'from_node': ('Vector.texcoord.Object',),
        'to_node': ('Vector.FS25_VehicleShader.Generated UV',),
        'inputs': {'Scale': (3.0, 3.0, 3.0)},  # Set tiling to match GE vehicle shader
    },
    'Detail Diffuse': {
        'location': (-500, 80),
        'bl_idname': 'ShaderNodeTexImage',
        'to_node': ('Color.FS25_VehicleShader.Detail Diffuse',),
        'from_node': ('Vector.detail_mapping.Vector',),
        'props': {'projection': 'BOX'},  # triplanar
        'image_key': 'detailDiffuse',
        'colorspace': 'Color',
        'collapsed': True,
        'hide_unused': True,
    },
    'Detail Specular': {
        'location': (-500, 40),
        'bl_idname': 'ShaderNodeTexImage',
        'to_node': ('Color.FS25_VehicleShader.Detail Specular',),
        'from_node': ('Vector.detail_mapping.Vector',),
        'props': {'projection': 'BOX'},  # triplanar
        'image_key': 'detailSpecular',
        'colorspace': 'Non-Color',
        'collapsed': True,
        'hide_unused': True,
    },
    'Detail Normal': {
        'location': (-500, 0),
        'bl_idname': 'ShaderNodeTexImage',
        'to_node': ('Color.FS25_VehicleShader.Detail Normal',),
        'from_node': ('Vector.detail_mapping.Vector',),
        'props': {'projection': 'BOX'},  # triplanar
        'image_key': 'detailNormal',
        'colorspace': 'Non-Color',
        'collapsed': True,
        'hide_unused': True,
    }
}

MASKS = {
    'Scratches': 'show_scratches',
    'Dirt': 'show_dirt',
    'Snow': 'show_snow',
    'Wetness': 'show_wetness',
    'Wetness Mask': 'show_wetness_mask',
}


def get_mat_and_shader(material: bpy.types.Material) -> tuple[dict, bpy.types.Node | None]:
    return material.i3d_attributes.shader_material_params, material.node_tree.nodes.get('FS25_VehicleShader')


def set_param(param: str, material: bpy.types.Material) -> None:
    i3d_params, vehicle_shader_node = get_mat_and_shader(material)

    if vehicle_shader_node is None:
        log_warning("FS25_VehicleShader node not found in the material.")
        return
    if (param_info := ATTR_MAP.get(param)) is None:
        return
    key, socket_name = param_info
    if key in i3d_params:
        if key == 'colorScale':
            i3d_params[key] = vehicle_shader_node.inputs[socket_name].default_value[0:3]
        else:
            i3d_params[key][0] = vehicle_shader_node.inputs[socket_name].default_value


def get_param(param: str, material: bpy.types.Material) -> None:
    i3d_params, vehicle_shader_node = get_mat_and_shader(material)

    if vehicle_shader_node is None:
        log_warning("FS25_VehicleShader node not found in the material.")
        return None

    if (param_info := ATTR_MAP.get(param)) is None:
        return
    key, socket_name = param_info

    if key in i3d_params:
        if key == 'colorScale':
            vehicle_shader_node.inputs[socket_name].default_value = i3d_params[key][0:3] + (1.0,)
        else:
            vehicle_shader_node.inputs[socket_name].default_value = i3d_params[key][0]
    return None


def get_set_params(material: bpy.types.Material, skip_color_scale: bool = False, only_color_scale: bool = False,
                   mode: str = 'GET') -> None:
    if mode not in {'GET', 'SET'}:
        log_warning(f"Invalid mode: {mode}. Use 'GET' or 'SET'.")
        return
    if not skip_color_scale:
        get_param('colorScale', material) if mode == 'GET' else set_param('colorScale', material)
    if only_color_scale:
        return

    get_param('smoothnessScale', material) if mode == 'GET' else set_param('smoothnessScale', material)
    get_param('metalnessScale', material) if mode == 'GET' else set_param('metalnessScale', material)
    get_param('clearCoatIntensity', material) if mode == 'GET' else set_param('clearCoatIntensity', material)
    get_param('clearCoatSmoothness', material) if mode == 'GET' else set_param('clearCoatSmoothness', material)
    get_param('porosity', material) if mode == 'GET' else set_param('porosity', material)


def import_shader(name='FS25_VehicleShader'):
    library = Path(__file__).parent / 'shader.blend'
    filepath = library / 'NodeTree' / name
    directory = library / 'NodeTree'
    bpy.ops.wm.append(
        filepath=str(filepath),
        filename=name,
        directory=str(directory)
    )


def check_i3dio_enabled() -> bool:
    return 'i3dio' in bpy.context.preferences.addons


def get_fs_data_path_from_i3dio() -> str | None:
    """Get the FS data path from the I3DIO addon."""
    addon = bpy.context.preferences.addons.get(I3DIO_ADDON_ID)
    if not addon:
        return None
    return addon.preferences.fs_data_path or None


def get_file_from_data(file_path: str | Path) -> Path:
    s = str(file_path)
    if s.startswith('$data'):
        return Path(get_fs_data_path_from_i3dio()) / s[6:]
    return Path(s)


def load_custom_image(image_path: str) -> bpy.types.Image | None:
    if image_path == '':
        return None
    image = bpy.data.images.get(str(Path(image_path).name))
    if image is None:
        image = bpy.data.images.get(str(Path(image_path).with_suffix('.dds').name))
    if image is None:
        fs_image_path = get_file_from_data(image_path)
        if not fs_image_path.exists():
            fs_image_path = image_path.replace('.png', '.dds')
        image = bpy.data.images.load(str(get_file_from_data(fs_image_path)))
    return image


def set_image(image: bpy.types.Image | None, image_node, color_space='Color'):
    try:
        image_node.image = image

        if color_space == 'Non-Color' and image_node.image:
            image_node.image.colorspace_settings.name = 'Non-Color'

    except RuntimeError:
        log_warning(f"Could not load image for node {getattr(image_node, 'name', '?')}")


def update_detail_map(mat: bpy.types.Material, mode='GET'):
    if mode not in {'GET', 'SET'}:
        log_warning(f"Invalid mode: {mode}. Use 'GET' or 'SET'.")
        return
    textures = mat.i3d_attributes.shader_material_textures
    if textures is None or len(textures) < 3:
        log_warning("No detail textures found in material attributes.")
        return

    if diffuse := mat.node_tree.nodes.get('Detail Diffuse'):
        if mode == 'GET':
            texture = mat.i3d_attributes.shader_material_textures[2]
            src_path = texture.source if texture.source else texture.default_source
            image = load_custom_image(src_path)
            set_image(image, diffuse)
        else:
            mat.i3d_attributes.shader_material_textures[2].source = diffuse.image.filepath if diffuse.image else ''

    if normal := mat.node_tree.nodes.get('Detail Normal'):
        if mode == 'GET':
            texture = mat.i3d_attributes.shader_material_textures[1]
            src_path = texture.source if texture.source else texture.default_source
            image = load_custom_image(src_path)
            set_image(image, normal, 'Non-Color')
        else:
            mat.i3d_attributes.shader_material_textures[1].source = normal.image.filepath if normal.image else ''

    if specular := mat.node_tree.nodes.get('Detail Specular'):
        if mode == 'GET':
            texture = mat.i3d_attributes.shader_material_textures[0]
            src_path = texture.source if texture.source else texture.default_source
            image = load_custom_image(src_path)
            set_image(image, specular, 'Non-Color')
        else:
            mat.i3d_attributes.shader_material_textures[0].source = specular.image.filepath if specular.image else ''

    if intensity := mat.node_tree.nodes.get('Lights Intensity'):
        log_warning("Updating Lights Intensity texture")
        if len(textures) >= 8:
            if textures[7].name == 'lightsIntensity':
                if mode == 'GET':
                    image = load_custom_image(mat.i3d_attributes.shader_material_textures[7].source)
                    set_image(image, intensity)
                else:
                    mat.i3d_attributes.shader_material_textures[7].source = intensity.image.filepath \
                        if intensity.image else ''


def _apply_props(node: bpy.types.Node, props: dict | None):
    if not props:
        return
    for attr, val in props.items():
        try:
            setattr(node, attr, val)
        except Exception:
            log_warning(f"Could not set prop {attr} on {node.name}")


def _apply_inputs(node: bpy.types.Node, inputs: dict | None):
    if not inputs:
        return
    for socket_name, val in inputs.items():
        socket = node.inputs.get(socket_name)
        if socket is None:
            continue
        try:
            socket.default_value = val
        except Exception:
            try:
                default_val = socket.default_value
                if isinstance(default_val, (tuple, list)) and isinstance(val, (tuple, list)):
                    for i in range(min(len(default_val), len(val))):
                        default_val[i] = val[i]
            except Exception:
                log_warning(f"Could not set input '{socket_name}' on {node.name}")


def set_role(node: bpy.types.Node, role: str) -> None:
    try:
        node[ROLE_PROP] = role
    except Exception:
        pass


def find_by_role(mat: bpy.types.Material, role: str) -> bpy.types.Node | None:
    # Prefer exact match on our role prop; fallback to name (for older materials)
    for n in mat.node_tree.nodes:
        if n.get(ROLE_PROP) == role:
            return n
    return mat.node_tree.nodes.get(role)


def set_node_and_links(mat: bpy.types.Material, role: str,
                       node: bpy.types.Node | None = None) -> bpy.types.Node | None:
    params = NODE_SETTINGS.get(role)
    if params is None:
        return None

    nodes = mat.node_tree.nodes
    created = False
    if node is None:
        node = nodes.get(role)
        if node is None:
            node = nodes.new(params['bl_idname'])
            created = True

    node.location = params['location']

    # Only rename if created (keep user/adopted names intact)
    if created:
        node.name = role
        node.label = role
        try:
            node["i3d_auto_created"] = True
        except Exception:
            pass

    set_role(node, role)

    # Handle NodeGroup 'group' by name
    group_name = params.get('group')
    if group_name and hasattr(node, "node_tree"):
        if nt := bpy.data.node_groups.get(group_name):
            node.node_tree = nt

    _apply_props(node, params.get('props'))
    _apply_inputs(node, params.get('inputs'))
    return node


def _refs_for(name: str) -> set[str]:
    refs = set()
    params = NODE_SETTINGS.get(name, {})
    for key in ('from_node', 'to_node'):
        for p in params.get(key, ()) or ():
            parts = p.split('.')
            if len(parts) == 3:
                refs.add(parts[1])  # Middle node name (other_name)
    return refs


def _closure_for(seeds: set[str]) -> list[str]:
    seen = set()
    stack = list(seeds)
    order = []
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        order.append(name)
        for ref in _refs_for(name):
            if ref not in seen:
                stack.append(ref)
    return order


def _resolve_source(tex) -> str:
    return tex.source if getattr(tex, 'source', '') else getattr(tex, 'default_source', '')


def _assign_image_for_role(mat: bpy.types.Material, node: bpy.types.Node, image_key: str | None,
                           default_image: str | None, colorspace: str = 'Color', optional: bool = False) -> None:
    if node.bl_idname != 'ShaderNodeTexImage':
        return

    # 1) Try explicit material texture slot via image_key
    if image_key:
        textures = getattr(mat.i3d_attributes, 'shader_material_textures', None)
        if textures and image_key in textures:
            path = _resolve_source(textures[image_key])
            if path:
                img = load_custom_image(path)
                set_image(img, node, colorspace)
                return
        elif image_key and not optional:
            log_warning(f"Texture key '{image_key}' not found for node '{getattr(node, 'name', '?')}'")

    # 2) Fallback to default_image if node has no image
    if not getattr(node, 'image', None) and default_image:
        img = load_custom_image(default_image)
        set_image(img, node, colorspace)


def assign_images_from_dict(mat: bpy.types.Material, nodes_by_role: dict[str, bpy.types.Node]) -> None:
    for role, params in NODE_SETTINGS.items():
        node = nodes_by_role.get(role) or find_by_role(mat, role)
        if not node:
            continue
        image_key = params.get('image_key')
        default_image = params.get('default_image')
        colorspace = params.get('colorspace', 'Color')
        optional = bool(params.get('optional', False))
        _assign_image_for_role(mat, node, image_key, default_image, colorspace, optional)


def apply_presentation_from_dict(mat: bpy.types.Material):
    """Apply presentation settings like collapsed and hide_unused from NODE_SETTINGS."""
    for role, params in NODE_SETTINGS.items():
        node = find_by_role(mat, role)
        if not node:
            continue
        if params.get('collapsed'):
            node.hide = True
        if params.get('hide_unused'):
            for sock in (*getattr(node, "inputs", []), *getattr(node, "outputs", [])):
                try:
                    sock.hide = not sock.is_linked
                except Exception:
                    pass


def adopt_existing_nodes(mat: bpy.types.Material) -> dict[str, bpy.types.Node]:
    """
    Detect common user setups and relabel their nodes to our canonical names
    so the builder reuses them instead of creating new ones.
    Returns a dict of adopted names -> node.
    """
    nodes = mat.node_tree.nodes
    adopted: dict[str, bpy.types.Node] = {}

    # Find Principled BSDF node (prefer the one connected to Material output if multiple)
    principled = next((n for n in nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
    if not principled:
        return adopted

    # Diffuse (Image -> Base Color)
    if (base := principled.inputs.get('Base Color')) and base.is_linked:
        src = base.links[0].from_node
        if src.bl_idname == 'ShaderNodeTexImage':
            set_role(src, 'Diffuse')
            adopted['Diffuse'] = src

    # Normal (Normal Map/Image -> Principled.Normal)
    if (nrm_in := principled.inputs.get('Normal')) and nrm_in.is_linked:
        src = nrm_in.links[0].from_node
        if src.bl_idname == 'ShaderNodeTexImage':
            set_role(src, 'Normal')
            adopted['Normal'] = src
        elif src.bl_idname == 'ShaderNodeNormalMap':
            set_role(src, 'Normal Map')
            adopted['Normal Map'] = src
            if (nrm_map := src.inputs.get('Color')) and nrm_map.is_linked:
                tex = nrm_map.links[0].from_node
                if tex and tex.bl_idname == 'ShaderNodeTexImage':
                    set_role(tex, 'Normal')
                    adopted['Normal'] = tex

    if (gloss := nodes.get('Glossmap')):
        if gloss.bl_idname == 'ShaderNodeTexImage':
            # Case 1: Image Texture named "Glossmap"
            # Treat it as the Specular image node but keep the original name (to not break user setups)
            set_role(gloss, 'Specular')
            adopted['Specular'] = gloss
        elif gloss.bl_idname == 'ShaderNodeSeparateColor':
            # Case 2: Separate RGB node named "Glossmap"
            adopted['Glossmap'] = gloss
            if (gloss_map := gloss.inputs.get('Color')) and gloss_map.is_linked:
                tex = gloss_map.links[0].from_node
                if tex and tex.bl_idname == 'ShaderNodeTexImage':
                    set_role(tex, 'Specular')
                    adopted['Specular'] = tex  # Keep original name
    else:
        # Case 3: Principled Specular IOR Level fed by Image/SeparateColor
        if (ior := principled.inputs.get('Specular IOR Level')) and ior.is_linked:
            src = ior.links[0].from_node
            if src.bl_idname == 'ShaderNodeSeparateColor' and 'Glossmap' not in adopted:
                set_role(src, 'Glossmap')
                adopted['Glossmap'] = src
                if (col := src.inputs.get('Color')) and col.is_linked:
                    tex = col.links[0].from_node
                    if tex and tex.bl_idname == 'ShaderNodeTexImage':
                        set_role(tex, 'Specular')
                        adopted['Specular'] = tex  # Keep original name
            elif src.bl_idname == 'ShaderNodeTexImage' and 'Specular' not in adopted:
                set_role(src, 'Specular')
                adopted['Specular'] = src

    return adopted


def build_nodes_by_role(mat: bpy.types.Material, adopted: dict[str, bpy.types.Node]) -> dict[str, bpy.types.Node]:
    by_role: dict[str, bpy.types.Node] = {}
    for role in NODE_SETTINGS.keys():
        by_role[role] = adopted.get(role) or find_by_role(mat, role)
    return by_role


def link_between_roles(mat: bpy.types.Material,
                       nodes_by_role: dict[str, bpy.types.Node],
                       node_role: str, path_: str, from_node=True) -> None:
    parts = path_.split('.')
    if len(parts) != 3:
        log_warning(f"Invalid link path {path_!r} for role {node_role!r} (expected 'A.B.C').")
        return
    a, other_role, c = parts

    node = nodes_by_role.get(node_role) or find_by_role(mat, node_role)
    other = nodes_by_role.get(other_role) or find_by_role(mat, other_role)
    if not node or not other:
        return

    dst = node.inputs.get(a) if from_node else other.inputs.get(c)
    src = other.outputs.get(c) if from_node else node.outputs.get(a)
    if not src or not dst:
        return
    try:
        mat.node_tree.links.new(src, dst)
    except Exception:
        # if input had an existing link, replace it
        try:
            for link in list(dst.links):
                mat.node_tree.links.remove(link)
            mat.node_tree.links.new(src, dst)
        except Exception:
            pass


def link_all_from_dict(mat: bpy.types.Material, nodes_by_role: dict[str, bpy.types.Node]) -> None:
    for role, params in NODE_SETTINGS.items():
        if not nodes_by_role.get(role):
            continue
        for p in params.get('from_node', ()) or ():
            link_between_roles(mat, nodes_by_role, role, p, from_node=True)
        for p in params.get('to_node', ()) or ():
            link_between_roles(mat, nodes_by_role, role, p, from_node=False)


def apply_locations_from_dict(mat: bpy.types.Material, nodes_by_role: dict[str, bpy.types.Node]) -> None:
    """
    Move nodes to the positions defined in NODE_SETTINGS.
    """
    for role, params in NODE_SETTINGS.items():
        node = nodes_by_role.get(role) or find_by_role(mat, role)
        print(f"Applying location for role {role}: node={node}")
        if not node:
            print(f" No node found for role {role}")
            continue
        loc = params.get('location')
        if loc:
            try:
                print(f" Setting location of {role} to {loc}")
                node.location = loc
            except Exception:
                pass


def visualize_material(mat: bpy.types.Material) -> None:
    if get_fs_data_path_from_i3dio() is None:
        log_warning("FS25 Data Path is not set. Please set it in the addon preferences.")
        return
    if 'FS25_VehicleShader' not in bpy.data.node_groups:
        import_shader()

    if 'FS25_VehicleShader' in mat.node_tree.nodes:
        return

    mat.use_nodes = True

    # Adopt existing nodes that user may already have added
    adopted = adopt_existing_nodes(mat)     # now tags roles internally
    nodes_by_role = build_nodes_by_role(mat, adopted)

    # Create any missing nodes (tagged with role)
    for role in _closure_for(set(NODE_SETTINGS.keys())):
        if not nodes_by_role.get(role):
            nodes_by_role[role] = set_node_and_links(mat, role, node=None)

    apply_locations_from_dict(mat, nodes_by_role)

    # Link after everything exists
    link_all_from_dict(mat, nodes_by_role)

    # Assign images (uses nodes_by_role, honors default/image_key/colorspace)
    assign_images_from_dict(mat, nodes_by_role)

    apply_presentation_from_dict(mat)


def update_visualize_material(self, context):
    if get_fs_data_path_from_i3dio() is None:
        bpy.ops.i3d_material_visualizer.warning_popup('INVOKE_DEFAULT', message="FS25 Data Path is not set. ")
        return
    mat: bpy.types.Material = self
    if self.i3d_visualized:
        if 'FS25_VehicleShader' in mat.node_tree.nodes:
            return
        visualize_material(mat)
        get_set_params(mat, mode='GET')
    else:
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        bsdf = next((n for n in nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
        mount = next((n for n in nodes if n.bl_idname == "ShaderNodeOutputMaterial"
                      and getattr(n, "is_active_output", False)), None)
        if 'FS25_VehicleShader' in nodes and bsdf and mount:
            bsdf_out = bsdf.outputs.get('BSDF')
            surf_in = mount.inputs.get('Surface')
            if bsdf_out and surf_in:
                try:
                    links.new(bsdf_out, surf_in)
                except Exception:
                    pass

            for n in [n for n in nodes if n.get("i3d_auto_created", False)]:
                nodes.remove(n)


def update_mask(arg):
    def update_(self, context):
        for mat in bpy.data.materials:
            if mat.i3d_attributes.shader_name == 'vehicleShader':
                if node := mat.node_tree.nodes.get('FS25_VehicleShader'):
                    node.inputs[arg].default_value = getattr(self, MASKS[arg])

    return update_


def log_warning(*args):
    logging.log(logging.WARNING, " ".join(map(str, args)))
