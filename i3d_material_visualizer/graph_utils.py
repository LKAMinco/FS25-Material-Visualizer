import bpy
from bpy_extras.node_utils import connect_sockets

from .constants import AUTO_FLAG, ROLE_PROP
from .specs import NodeSpec


def ensure_node(mat: bpy.types.Material, spec: NodeSpec) -> bpy.types.Node:
    """Ensure a node of the given spec exists in the material's node tree."""
    nodes = mat.node_tree.nodes
    node = nodes.get(spec.role)
    if not node:
        node = nodes.new(spec.bl_idname)
        node.name = node.label = spec.role
        try:
            node[AUTO_FLAG] = True
        except Exception:
            pass
    if spec.group and hasattr(node, "node_tree"):
        nt = bpy.data.node_groups.get(spec.group)
        if nt:
            node.node_tree = nt
    for k, v in spec.props.items():
        try:
            setattr(node, k, v)
        except Exception:
            print(f"Could not set prop {k} on {node.name}")
    for name, val in spec.inputs_defaults.items():
        sock = node.inputs.get(name)
        if sock is None:
            continue
        _safe_assign(sock, val)
    try:
        node[ROLE_PROP] = spec.role
    except Exception:
        pass
    return node


def _safe_assign(sock: bpy.types.NodeSocket, val: object) -> None:
    """Assign value to socket default_value, handling different types safely."""
    try:
        sock.default_value = val
    except Exception:
        try:
            default_val = sock.default_value
            if isinstance(default_val, (tuple, list)) and isinstance(val, (tuple, list)):
                for i in range(min(len(default_val), len(val))):
                    default_val[i] = val[i]
        except Exception:
            pass


def find_socket(node: bpy.types.Node, name: str, is_input: bool = True) -> bpy.types.NodeSocket | None:
    """Find a socket by name on a node."""
    col = node.inputs if is_input else node.outputs
    return col.get(name)


def link_sockets(
    this_node: bpy.types.Node,
    other_node: bpy.types.Node,
    this_sock_name: str,
    other_sock_name: str,
    from_node: bool = True,
) -> None:
    """Link sockets between two nodes based on socket names and direction."""
    src_sock = (
        find_socket(other_node, other_sock_name, is_input=False)
        if from_node
        else find_socket(this_node, this_sock_name, is_input=False)
    )
    dst_sock = (
        find_socket(this_node, this_sock_name, is_input=True)
        if from_node
        else find_socket(other_node, other_sock_name, is_input=True)
    )
    if src_sock and dst_sock:
        connect_sockets(src_sock, dst_sock)


def apply_presentation(node: bpy.types.Node, spec: NodeSpec) -> None:
    """Apply presentation settings from spec to node."""
    if spec.collapsed:
        node.hide = True
    if spec.hide_unused:
        for s in (*node.inputs, *node.outputs):
            try:
                s.hide = not s.is_linked
            except Exception:
                pass
    if spec.set_active_output:
        try:
            node.is_active_output = True
        except Exception:
            pass


def remove_auto_nodes(mat: bpy.types.Material) -> None:
    """Remove nodes that were automatically created by the visualizer."""
    nodes = mat.node_tree.nodes
    for n in [n for n in nodes if n.get(AUTO_FLAG)]:
        nodes.remove(n)


def parse_link_path(path: str) -> tuple[str, str, str] | None:
    """Parse a link path string into its components."""
    try:
        a, b, c = path.split(".", 2)
        return a, b, c
    except ValueError:
        return None
