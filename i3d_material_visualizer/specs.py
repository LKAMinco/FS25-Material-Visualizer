from dataclasses import dataclass, field

from .constants import VEHICLE_SHADER_GROUP_NAME

Vec2 = tuple[int, int]


@dataclass(frozen=True)
class Link:  # "A.B.C" -> this.A <-> other.B.C
    path: str
    from_node: bool = True  # True: this ; False: this -> other
    condition: str | None = None  # only link if condition prop is True


@dataclass(frozen=True)
class ImageSpec:
    key: str | None = None
    default: str | None = None
    colorspace: str = "Color"
    optional: bool = False


@dataclass(frozen=True)
class NodeSpec:
    role: str
    bl_idname: str
    location: Vec2 | None = None
    location_relative_to: str | None = None  # role of node to offset from
    group: str | None = None
    inputs_defaults: dict[str, object] = field(default_factory=dict)
    props: dict[str, object] = field(default_factory=dict)
    to_node: list[Link] = field(default_factory=list)
    from_node: list[Link] = field(default_factory=list)
    collapsed: bool = False
    hide_unused: bool = False
    set_active_output: bool = False
    image: ImageSpec | None = None
    only_if_adopted: bool = False


SPECS: dict[str, NodeSpec] = {
    "Principled BSDF": NodeSpec(
        role="Principled BSDF",
        bl_idname="ShaderNodeBsdfPrincipled",
        from_node=[
            Link("Normal.Normal Map.Normal"),
            Link("Base Color.Diffuse.Color"),
            Link("Specular IOR Level.Specular.Color", condition="glossmap_missing"),
        ],
    ),
    "FS25_VehicleShader": NodeSpec(
        role="FS25_VehicleShader",
        bl_idname="ShaderNodeGroup",
        group=VEHICLE_SHADER_GROUP_NAME,
        location_relative_to="Principled BSDF",
        location=(0, -680),
        to_node=[Link("BSDF.Visualizer Material Output.Surface", from_node=False)],
        from_node=[
            Link("Detail Diffuse.Detail Diffuse.Color"),
            Link("Detail Specular.Detail Specular.Color"),
            Link("Detail Normal.Detail Normal.Color"),
            Link("Vector.detail_mapping.Generated UV"),
            Link("uv0.uv_diff.UV"),
            Link("uv1.uv_spec.UV"),
            Link("uv2.uv_norm.UV"),
        ],
        hide_unused=True,
    ),
    "Visualizer Material Output": NodeSpec(
        role="Visualizer Material Output",
        bl_idname="ShaderNodeOutputMaterial",
        location_relative_to="FS25_VehicleShader",
        location=(260, 0),
        from_node=[Link("Surface.FS25_VehicleShader.BSDF")],
        set_active_output=True,
    ),
    "Glossmap": NodeSpec(
        role="Glossmap",
        bl_idname="ShaderNodeSeparateColor",
        location_relative_to="Principled BSDF",
        location=(-160, 20),
        from_node=[Link("Color.Specular.Color")],
        collapsed=True,
        only_if_adopted=True,
    ),
    "Diffuse": NodeSpec(
        role="Diffuse",
        bl_idname="ShaderNodeTexImage",
        location_relative_to="Principled BSDF",
        location=(-420, 80),
        to_node=[
            Link("Color.Principled BSDF.Base Color", from_node=False),
            Link("Color.FS25_VehicleShader.Diffuse", from_node=False),
            Link("Alpha.FS25_VehicleShader.Alpha", from_node=False),
        ],
        from_node=[Link("Vector.uv_diff.UV")],
        image=ImageSpec(
            key=None,
            default="$data/shared/white_diffuse.dds",
            colorspace="Color",
            optional=False,
        ),
    ),
    "Specular": NodeSpec(
        role="Specular",
        bl_idname="ShaderNodeTexImage",
        location_relative_to="Principled BSDF",
        location=(-420, -480),
        to_node=[
            Link("Color.Glossmap.Color", from_node=False, condition="glossmap_exists"),
            Link("Color.FS25_VehicleShader.Specular", from_node=False),
        ],
        from_node=[Link("Vector.uv_spec.UV")],
        image=ImageSpec(
            key=None,
            default="$data/shared/default_vmask.dds",
            colorspace="Non-Color",
            optional=False,
        ),
    ),
    "Normal Map": NodeSpec(
        role="Normal Map",
        bl_idname="ShaderNodeNormalMap",
        location_relative_to="Principled BSDF",
        location=(-160, -180),
        to_node=[Link("Normal.Principled BSDF.Normal", from_node=False)],
        from_node=[Link("Color.Normal.Color")],
        collapsed=True,
    ),
    "Normal": NodeSpec(
        role="Normal",
        bl_idname="ShaderNodeTexImage",
        location_relative_to="Principled BSDF",
        location=(-420, -200),
        to_node=[
            Link("Color.Normal Map.Color", from_node=False),
            Link("Color.FS25_VehicleShader.Normal", from_node=False),
        ],
        from_node=[Link("Vector.uv_norm.UV")],
        image=ImageSpec(
            key=None,
            default="$data/shared/default_normal.dds",
            colorspace="Non-Color",
            optional=False,
        ),
    ),
    "Lights Intensity": NodeSpec(
        role="Lights Intensity",
        bl_idname="ShaderNodeTexImage",
        location_relative_to="Principled BSDF",
        location=(-420, -760),
        to_node=[Link("Color.FS25_VehicleShader.Lights Intensity", from_node=False)],
        from_node=[Link("Vector.uv_spec.UV")],
        image=ImageSpec(
            key="lightsIntensity",
            default=None,
            colorspace="Color",
            optional=True,
        ),
    ),
    # --- UV helpers ---
    "uv_diff": NodeSpec(
        role="uv_diff",
        bl_idname="ShaderNodeUVMap",
        location_relative_to="Principled BSDF",
        location=(-760, -560),
        to_node=[Link("UV.Diffuse.Vector", from_node=False)],
        collapsed=True,
    ),
    "uv_spec": NodeSpec(
        role="uv_spec",
        bl_idname="ShaderNodeUVMap",
        location_relative_to="Principled BSDF",
        location=(-760, -600),
        to_node=[
            Link("UV.Specular.Vector", from_node=False),
            Link("UV.Lights Intensity.Vector", from_node=False),
        ],
        collapsed=True,
    ),
    "uv_norm": NodeSpec(
        role="uv_norm",
        bl_idname="ShaderNodeUVMap",
        location_relative_to="Principled BSDF",
        location=(-760, -640),
        to_node=[Link("UV.Normal.Vector", from_node=False)],
        collapsed=True,
    ),
    "texcoord": NodeSpec(
        role="texcoord",
        bl_idname="ShaderNodeTexCoord",
        location_relative_to="Principled BSDF",
        location=(-840, -960),
        hide_unused=True,
    ),
    "detail_mapping": NodeSpec(
        role="detail_mapping",
        bl_idname="ShaderNodeMapping",
        location_relative_to="Principled BSDF",
        location=(-680, -960),
        from_node=[Link("Vector.texcoord.Object")],
        to_node=[Link("Vector.FS25_VehicleShader.Generated UV", from_node=False)],
        inputs_defaults={"Scale": (3.0, 3.0, 3.0)},
    ),
    "Detail Diffuse": NodeSpec(
        role="Detail Diffuse",
        bl_idname="ShaderNodeTexImage",
        location_relative_to="Principled BSDF",
        location=(-420, -1060),
        to_node=[Link("Color.FS25_VehicleShader.Detail Diffuse", from_node=False)],
        from_node=[Link("Vector.detail_mapping.Vector")],
        props={"projection": "BOX"},
        image=ImageSpec(
            key="detailDiffuse",
            default=None,
            colorspace="Color",
            optional=False,
        ),
        collapsed=True,
        hide_unused=True,
    ),
    "Detail Specular": NodeSpec(
        role="Detail Specular",
        bl_idname="ShaderNodeTexImage",
        location_relative_to="Principled BSDF",
        location=(-420, -1100),
        to_node=[Link("Color.FS25_VehicleShader.Detail Specular", from_node=False)],
        from_node=[Link("Vector.detail_mapping.Vector")],
        props={"projection": "BOX"},
        image=ImageSpec(
            key="detailSpecular",
            default=None,
            colorspace="Non-Color",
            optional=False,
        ),
        collapsed=True,
        hide_unused=True,
    ),
    "Detail Normal": NodeSpec(
        role="Detail Normal",
        bl_idname="ShaderNodeTexImage",
        location_relative_to="Principled BSDF",
        location=(-420, -1140),
        to_node=[Link("Color.FS25_VehicleShader.Detail Normal", from_node=False)],
        from_node=[Link("Vector.detail_mapping.Vector")],
        props={"projection": "BOX"},
        image=ImageSpec(
            key="detailNormal",
            default=None,
            colorspace="Non-Color",
            optional=False,
        ),
        collapsed=True,
        hide_unused=True,
    ),
}
