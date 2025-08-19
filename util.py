import logging
import bpy
from pathlib import Path

ATTR_MAP = dict[str, tuple[str, str]](
    colorScale=('colorScale', 'Color'),
    smoothnessScale=('smoothnessScale', 'Smoothness Scale'),
    metalnessScale=('metalnessScale', 'Metalness Scale'),
    clearCoatIntensity=('clearCoatIntensity', 'Clear Coat Intensity'),
    clearCoatSmoothness=('clearCoatSmoothness', 'Clear Coat Smoothness'),
    porosity=('porosity', 'Porosity'),
)

NODE_SETTINGS = {
    'Principled BSDF': {
        'location': (200, 440),
        'type': 'ShaderNodeBsdfPrincipled',
        'from_node': ('Normal.Normal Map.Normal', 'Base Color.Diffuse.Color',),
    },
    'Material Output': {
        'location': (700, 260),
        'type': 'ShaderNodeOutputMaterial',
        'from_node': ('Surface.FS25_VehicleShader.BSDF',),
    },
    'FS25_VehicleShader': {
        'location': (280, 240),
        'type': 'ShaderNodeGroup',
        'group': 'FS25_VehicleShader',
        'to_node': ('BSDF.Material Output.Surface', 'Resolution.point0'),
        'from_node': ('Diffuse.Diffuse.Color',
                      'Specular.Specular.Color',
                      'Normal.Normal.Color',
                      'Alpha.Diffuse.Color',
                      'Detail Diffuse.Detail Diffuse.Color',
                      'Detail Specular.Detail Specular.Color',
                      'Detail Normal.Detail Normal.Color'
                      'uv0.uv0_diff.Vector',
                      'uv1.uv1_spec.Vector',
                      'uv2.uv2_norm.Vector',),
    },
    'Normal Map': {
        'location': (-20, 380),
        'type': 'ShaderNodeNormalMap',
        'to_node': ('Normal.Principled BSDF.Normal',),
        'from_node': ('Color.Normal.Color',),
    },
    'Glossmap': {
        'location': (-20, 340),
        'type': 'ShaderNodeSeparateColor',
        'from_node': ('Color.Specular.Color',),
    },
    'Basemap': {
        'location': (-20, 300),
        'type': 'ShaderNodeCombineXYZ',
        'from_node': ('X.Diffuse.Color', 'Y.Specular.Color', 'Z.Normal.Color'),
    },
    'Detailmap': {
        'location': (-20, 0),
        'type': 'ShaderNodeCombineXYZ',
        'from_node': ('X.Detail Diffuse.Color', 'Y.Detail Specular.Color', 'Z.Detail Normal.Color'),
    },
    'Diffuse': {
        'location': (-600, 400),
        'type': 'ShaderNodeTexImage',
        'to_node': ('Color.Basemap.X', 'Color.Principled BSDF.Base Color', 'Color.FS25_VehicleShader.Diffuse'),
        'from_node': ('Vector.uv0_diff.UV',),
    },
    'Specular': {
        'location': (-600, 340),
        'type': 'ShaderNodeTexImage',
        'to_node': ('Color.Basemap.Y', 'Color.Glossmap.Color', 'Color.FS25_VehicleShader.Specular',),
        'from_node': ('Vector.uv1_spec.UV',),
    },
    'Normal': {
        'location': (-600, 280),
        'type': 'ShaderNodeTexImage',
        'to_node': ('Color.Basemap.Z', 'Color.Normal Map.Color', 'Color.FS25_VehicleShader.Normal'),
        'from_node': ('Vector.uv2_norm.UV',),
    },
    'Lights Intensity': {
        'location': (-600, 120),
        'type': 'ShaderNodeTexImage',
        'to_node': ('Color.FS25_VehicleShader.Lights Intensity',),
        'from_node': ('Vector.uv1_spec.UV',),
    },
    'uv0_diff': {
        'location': (-800, 420),
        'type': 'ShaderNodeUVMap',
        'to_node': ('UV.Diffuse.Vector',),
        'preferred_uv': 0,
    },
    'uv1_spec': {
        'location': (-800, 360),
        'type': 'ShaderNodeUVMap',
        'to_node': ('UV.Specular.Vector', 'UV.Lights Intensity.Vector',),
        'preferred_uv': 1,
    },
    'uv2_norm': {
        'location': (-800, 300),
        'type': 'ShaderNodeUVMap',
        'to_node': ('UV.Normal.Vector',),
        'preferred_uv': 2,
    },
    'Detail Diffuse': {
        'location': (-600, 60),
        'type': 'ShaderNodeTexImage',
        'to_node': ('Color.Detailmap.X', 'Color.FS25_VehicleShader.Detail Diffuse'),
        'from_node': ('Vector.map_diff.Vector',),
    },
    'Detail Specular': {
        'location': (-600, 20),
        'type': 'ShaderNodeTexImage',
        'to_node': ('Color.Detailmap.Y', 'Color.FS25_VehicleShader.Detail Specular'),
        'from_node': ('Vector.map_spec.Vector',),
    },
    'Detail Normal': {
        'location': (-600, -20),
        'type': 'ShaderNodeTexImage',
        'to_node': ('Color.Detailmap.Z', 'Color.FS25_VehicleShader.Detail Normal'),
        'from_node': ('Vector.map_norm.Vector',),
    },
    'map_diff': {
        'location': (-820, 120),
        'type': 'ShaderNodeMapping',
        'to_node': ('Vector.Detail Diffuse.Vector',),
        'from_node': ('Vector.uv0_detailDiff.UV',),
    },
    'map_spec': {
        'location': (-820, 60),
        'type': 'ShaderNodeMapping',
        'to_node': ('Vector.Detail Specular.Vector',),
        'from_node': ('Vector.uv1_detailSpec.UV',),
    },
    'map_norm': {
        'location': (-820, 0),
        'type': 'ShaderNodeMapping',
        'to_node': ('Vector.Detail Normal.Vector',),
        'from_node': ('Vector.uv2_detailNorm.UV',),
    },
    'uv0_detailDiff': {
        'location': (-1020, 140),
        'type': 'ShaderNodeUVMap',
        'to_node': ('UV.map_diff.Vector', 'UV.FS25_VehicleShader.uv0'),
        'preferred_uv': 0,
    },
    'uv1_detailSpec': {
        'location': (-1020, 80),
        'type': 'ShaderNodeUVMap',
        'to_node': ('UV.map_spec.Vector', 'UV.FS25_VehicleShader.uv1'),
        'preferred_uv': 1,
    },
    'uv2_detailNorm': {
        'location': (-1020, 20),
        'type': 'ShaderNodeUVMap',
        'to_node': ('UV.map_norm.Vector', 'UV.FS25_VehicleShader.uv2'),
        'preferred_uv': 2,
    },
    'point0': {
        'location': (460, 180),
        'type': 'NodeReroute',
        'from_node': ('Resolution.FS25_VehicleShader',),
        'to_node': ('point1',),
    },
    'point1': {
        'location': (460, -100),
        'type': 'NodeReroute',
        'from_node': ('point0',),
        'to_node': ('point2',),
    },
    'point2': {
        'location': (-1100, -100),
        'type': 'NodeReroute',
        'from_node': ('point1',),
        'to_node': ('point3',),
    },
    'point3': {
        'location': (-1100, -20),
        'type': 'NodeReroute',
        'from_node': ('point2',),
        'to_node': ('point4', 'Scale.map_norm'),
    },
    'point4': {
        'location': (-1100, 40),
        'type': 'NodeReroute',
        'from_node': ('point3',),
        'to_node': ('point5', 'Scale.map_spec'),
    },
    'point5': {
        'location': (-1100, 100),
        'type': 'NodeReroute',
        'from_node': ('point4',),
        'to_node': ('point6', 'Scale.map_diff'),
    },
}

REMOVABLE_NODES = ['FS25_VehicleShader',
                   'Detailmap',
                   'Detail Diffuse',
                   'Detail Normal',
                   'Detail Specular',
                   'Lights Intensity',
                   'Basemap',
                   'map_diff',
                   'map_spec',
                   'map_norm',
                   'uv0_detailDiff',
                   'uv2_detailNorm',
                   'uv1_detailSpec',
                   'uv0_diff',
                   'uv1_spec',
                   'uv2_norm',
                   'point5',
                   'point4',
                   'point3',
                   'point2',
                   'point1',
                   'point0']

MASKS = {
    'Scratches': 'show_scratches',
    'Dirt': 'show_dirt',
    'Snow': 'show_snow',
    'Wetness': 'show_wetness',
    'Wetness Mask': 'show_wetness_mask',
}


def get_mat_and_shader(material=None):
    if material is None:
        i3d_params = bpy.context.object.active_material.i3d_attributes.shader_material_params
        vehicle_shader = bpy.context.object.active_material.node_tree.nodes.get('FS25_VehicleShader')
    else:
        i3d_params = material.i3d_attributes.shader_material_params
        vehicle_shader = material.node_tree.nodes.get('FS25_VehicleShader')

    return i3d_params, vehicle_shader


def set_param(param: str, material=None):
    i3d_params, vehicle_shader = get_mat_and_shader(material)

    if vehicle_shader is None:
        print("FS25_VehicleShader node not found in the material.")
        return None
    param = ATTR_MAP.get(param, None)
    if param[0] in i3d_params:
        if param[0] == 'colorScale':
            i3d_params[param[0]] = vehicle_shader.inputs[param[1]].default_value[0:3]
        else:
            i3d_params[param[0]][0] = vehicle_shader.inputs[param[1]].default_value


def get_param(param: str, material=None):
    i3d_params, vehicle_shader = get_mat_and_shader(material)

    if vehicle_shader is None:
        print("FS25_VehicleShader node not found in the material.")
        return None

    param = ATTR_MAP.get(param, None)
    if param[0] in i3d_params:
        if param[0] == 'colorScale':
            vehicle_shader.inputs[param[1]].default_value = i3d_params[param[0]][0:3] + (1.0,)
        else:
            vehicle_shader.inputs[param[1]].default_value = i3d_params[param[0]][0]
    return None


def get_set_params(skip_color_scale=False, only_color_scale=False, mode='GET', material=None):
    if material is None:
        material = bpy.context.object.active_material
    if mode not in {'GET', 'SET'}:
        print(f"Invalid mode: {mode}. Use 'GET' or 'SET'.")
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


def get_fs25_data_path():
    preferences = bpy.context.preferences
    addon_prefs = preferences.addons[__package__].preferences
    if addon_prefs is None:
        return None
    return None if addon_prefs.fs25_data_path == '' else addon_prefs.fs25_data_path


def get_file_from_data(file_path):
    if str(file_path).startswith('$data'):
        return Path(get_fs25_data_path()) / Path(file_path[6:])
    return Path(file_path)


def load_custom_image(image_path):
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


def set_image(image, image_node, color_space='Color'):
    try:
        image_node.image = image

        if color_space == 'Non-Color':
            image_node.image.colorspace_settings.name = 'Non-Color'

    except RuntimeError:
        print(f"Could not load image {image.name} from {image.filepath}")


def update_detail_map(mat, mode='GET'):
    if mode not in {'GET', 'SET'}:
        print(f"Invalid mode: {mode}. Use 'GET' or 'SET'.")
        return
    textures = mat.i3d_attributes.shader_material_textures
    if textures is None or len(textures) < 3:
        print("No detail textures found in material attributes.")
        return

    if diffuse := mat.node_tree.nodes.get('Detail Diffuse'):
        if mode == 'GET':
            image = load_custom_image(mat.i3d_attributes.shader_material_textures[2].source)
            set_image(image, diffuse)
        else:
            mat.i3d_attributes.shader_material_textures[2].source = diffuse.image.filepath if diffuse.image else ''

    if normal := mat.node_tree.nodes.get('Detail Normal'):
        if mode == 'GET':
            image = load_custom_image(mat.i3d_attributes.shader_material_textures[1].source)
            set_image(image, normal, 'Non-Color')
        else:
            mat.i3d_attributes.shader_material_textures[1].source = normal.image.filepath if normal.image else ''

    if specular := mat.node_tree.nodes.get('Detail Specular'):
        if mode == 'GET':
            image = load_custom_image(mat.i3d_attributes.shader_material_textures[0].source)
            set_image(image, specular, 'Non-Color')
        else:
            mat.i3d_attributes.shader_material_textures[0].source = specular.image.filepath if specular.image else ''

    if intensity := mat.node_tree.nodes.get('Lights Intensity'):
        print("Updating Lights Intensity texture")
        if len(textures) >= 8:
            if textures[7].name == 'lightsIntensity':
                if mode == 'GET':
                    image = load_custom_image(mat.i3d_attributes.shader_material_textures[7].source)
                    set_image(image, intensity)
                else:
                    mat.i3d_attributes.shader_material_textures[7].source = intensity.image.filepath \
                        if intensity.image else ''


def link_node(node, path_, mat, from_node=True):
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    is_point = 'point' in node.name
    path_ = path_.split('.')

    if is_point:
        if len(path_) == 2:
            src = path_[0]
            src_node = nodes.get(path_[1])
            if src_node is None:
                return
            if from_node:
                src_socket = src_node.outputs.get(src)
                dst_socket = node.inputs[0]
            else:
                src_socket = node.outputs[0]
                dst_socket = src_node.inputs.get(src)
            links.new(src_socket, dst_socket)
        elif len(path_) == 1:
            src = nodes.get(path_[0])
            if src is None:
                return
            if from_node:
                src_socket = src.inputs[0]
                dst_socket = node.outputs[0]
            else:
                src_socket = node.outputs[0]
                dst_socket = src.inputs[0]

            links.new(src_socket, dst_socket)
        else:
            print(f'Invalid point path {path_}')
            return
        return

    dst_node = nodes.get(path_[1])
    if dst_node is None:
        return

    src = path_[0]
    dst = path_[2]

    # from = my socket - node - from socket -> inputs to me
    # to = my socket - node - from socket -> outputs from me

    if from_node:
        src_socket = dst_node.outputs.get(dst)
        dst_socket = node.inputs.get(src)
    else:
        src_socket = node.outputs.get(src)
        dst_socket = dst_node.inputs.get(dst)

    if src_socket is None or dst_socket is None:
        print(
            f'Invalid path {path_} node: {node.name} dst_node: {dst_node.name}\n src_socket: {src_socket} dst_socket: {dst_socket}')
        return

    links.new(src_socket, dst_socket)


def set_node_and_links(mat, name, node=None):
    node_params = NODE_SETTINGS.get(name)
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    if node_params is None:
        return None

    if node is None:
        node = nodes.get(name)
        if node is None:
            node = nodes.new(node_params['type'])

    location = node_params['location']
    node.location = location
    node.name = name
    node.label = name

    # clear_node_links(node, links)

    from_node = node_params.get('from_node')
    if from_node is not None:
        for path_ in from_node:
            link_node(node, path_, mat)

    to_node = node_params.get('to_node')
    if to_node is not None:
        for path_ in to_node:
            link_node(node, path_, mat, from_node=False)

    uv = node_params.get('preferred_uv')
    if uv is not None:
        obj = bpy.context.object
        if uv < len(obj.data.uv_layers):
            node.uv_map = obj.data.uv_layers[uv].name
        else:
            node.uv_map = obj.data.uv_layers[0].name

    return node


def visualize_material(mat):
    if get_fs25_data_path() is None:
        print("FS25 Data Path is not set. Please set it in the addon preferences.")
        return
    white_diffuse = '$data/shared/white_diffuse.dds'
    if 'white_diffuse.dds' not in bpy.data.images:
        load_custom_image(white_diffuse)
    white_image = bpy.data.images.get('white_diffuse.dds')
    if 'FS25_VehicleShader' not in bpy.data.node_groups:
        import_shader()

    if 'FS25_VehicleShader' in mat.node_tree.nodes:
        return
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    resolution = None

    principled_bsdf = set_node_and_links(mat, 'Principled BSDF')
    set_node_and_links(mat, 'Material Output')

    fs25_shader = nodes.new('ShaderNodeGroup')
    fs25_shader.node_tree = bpy.data.node_groups.get('FS25_VehicleShader')
    set_node_and_links(mat, 'FS25_VehicleShader', fs25_shader)

    set_node_and_links(mat, 'Basemap')

    # Diffuse
    if principled_bsdf.inputs.get('Base Color').links:
        diffuse = principled_bsdf.inputs['Base Color'].links[0].from_node
        set_node_and_links(mat, 'Diffuse', diffuse)
    else:
        diffuse = set_node_and_links(mat, 'Diffuse')

    if diffuse.inputs.get('Vector').links:
        uv = diffuse.inputs['Vector'].links[0].from_node
        set_node_and_links(mat, 'uv0_diff', uv)
    else:
        set_node_and_links(mat, 'uv0_diff')

    # Alpha
    alpha = principled_bsdf.inputs.get('Alpha')
    if alpha.links:
        links.new(fs25_shader.inputs['Alpha'], alpha.links[0].from_socket)
    else:
        diffuse = nodes.get('Diffuse')
        if diffuse.image is not None:
            links.new(fs25_shader.inputs['Alpha'], diffuse.outputs['Alpha'])
        else:
            diffuse.image = white_image

    # Emission
    emission = principled_bsdf.inputs[27]
    if emission.links:
        links.new(fs25_shader.inputs['Lights Intensity'], emission.links[0].from_socket)
        emission.links[0].from_node.location = (-600, 120)
    else:
        if len(mat.i3d_attributes.shader_material_textures) >= 8:
            if mat.i3d_attributes.shader_material_textures[7].name == 'lightsIntensity':
                lights_intensity = set_node_and_links(mat, 'Lights Intensity')
                lights_intensity.image = load_custom_image(
                    mat.i3d_attributes.shader_material_textures[7].source
                    if mat.i3d_attributes.shader_material_textures[7].source else
                    mat.i3d_attributes.shader_material_textures[7].default_source)
                if lights_intensity.inputs.get('Vector').links:
                    uv = lights_intensity.inputs['Vector'].links[0].from_node
                    set_node_and_links(mat, 'uv1_spec', uv)
                else:
                    set_node_and_links(mat, 'uv1_spec')

    # Specular
    gloss_map = set_node_and_links(mat, 'Glossmap')
    if gloss_map.inputs.get('Color').links:
        specular = gloss_map.inputs['Color'].links[0].from_node
        set_node_and_links(mat, 'Specular', specular)
    else:
        specular = set_node_and_links(mat, 'Specular')

    if specular.image is not None:
        specular.image.colorspace_settings.name = 'Non-Color'

    if resolution is None:
        if specular.image is not None:
            resolution = specular.image.size[0], specular.image.size[1]

    if specular.inputs.get('Vector').links:
        uv = specular.inputs['Vector'].links[0].from_node
        set_node_and_links(mat, 'uv1_spec', uv)
    else:
        set_node_and_links(mat, 'uv1_spec')

    # Normal
    normal_map = set_node_and_links(mat, 'Normal Map')
    if normal_map.inputs.get('Color').links:
        normal = normal_map.inputs['Color'].links[0].from_node
        set_node_and_links(mat, 'Normal', normal)
    else:
        normal = set_node_and_links(mat, 'Normal')

    if normal.image is not None:
        normal.image.colorspace_settings.name = 'Non-Color'

    if resolution is None:
        if normal.image is not None:
            resolution = normal.image.size[0], normal.image.size[1]

    if normal.inputs.get('Vector').links:
        uv = normal.inputs['Vector'].links[0].from_node
        set_node_and_links(mat, 'uv2_norm', uv)
    else:
        set_node_and_links(mat, 'uv2_norm')

    if resolution:
        scale = max(max(resolution[0], resolution[1]) / 256.0, 1.0)
        fs25_shader.inputs['Resolution'].default_value = resolution[0], resolution[1], scale * 2.0
        fs25_shader.inputs['Droplets Scale'].default_value = 1

    set_node_and_links(mat, 'Detailmap')
    detail_diffuse = set_node_and_links(mat, 'Detail Diffuse')
    detail_secular = set_node_and_links(mat, 'Detail Specular')
    detail_normal = set_node_and_links(mat, 'Detail Normal')

    textures = mat.i3d_attributes.shader_material_textures
    detail_diffuse.image = load_custom_image(textures[2].source if textures[2].source else textures[2].default_source)
    detail_secular.image = load_custom_image(textures[0].source if textures[0].source else textures[0].default_source)
    detail_normal.image = load_custom_image(textures[1].source if textures[1].source else textures[1].default_source)
    detail_normal.image.colorspace_settings.name = 'Non-Color'
    detail_secular.image.colorspace_settings.name = 'Non-Color'

    set_node_and_links(mat, 'map_diff')
    set_node_and_links(mat, 'map_spec')
    set_node_and_links(mat, 'map_norm')
    set_node_and_links(mat, 'uv0_detailDiff')
    set_node_and_links(mat, 'uv1_detailSpec')
    set_node_and_links(mat, 'uv2_detailNorm')

    set_node_and_links(mat, 'point5')
    set_node_and_links(mat, 'point4')
    set_node_and_links(mat, 'point3')
    set_node_and_links(mat, 'point2')
    set_node_and_links(mat, 'point1')
    set_node_and_links(mat, 'point0')

    for node in nodes:
        node.hide = True


def update_visualize_material(self, context):
    mat = self
    if self.i3d_visualized:
        if 'FS25_VehicleShader' in mat.node_tree.nodes:
            return
        visualize_material(mat)
        get_set_params(mode='GET', material=mat)
    else:
        nodes = self.node_tree.nodes
        links = self.node_tree.links
        if 'FS25_VehicleShader' in nodes:
            if 'Principled BSDF' in nodes:
                links.new(nodes['Principled BSDF'].outputs['BSDF'], nodes['Material Output'].inputs['Surface'])

            for node in nodes:
                if node.name in REMOVABLE_NODES:
                    nodes.remove(node)


def update_mask(arg):
    def update_(self, context):
        for mat in bpy.data.materials:
            if mat.i3d_attributes.shader_name == 'vehicleShader':
                if node := mat.node_tree.nodes.get('FS25_VehicleShader'):
                    node.inputs[arg].default_value = getattr(self, MASKS[arg])

    return update_


def print(*args):
    logging.log(logging.WARNING, " ".join(map(str, args)))
