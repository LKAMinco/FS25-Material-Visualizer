# FS25 Vehicle Shader Visualizer

### Supports only [Unofficial I3D Exporter](https://github.com/StjerneIdioten/I3D-Blender-Addon/releases)

### !!! For correct work, fs25 data path must be set in Blender preferences.

This mod visualizes the vehicle shader in Farming Simulator 25. It allows you to see how the shader is applied to
vehicles in the game.

When material is visualized, all properties can be controlled via Giants shader or Material shader.
Properties can be transferred between shaders via Get / Set controls.
Properties can be transferred same as material templates are loaded into giants shader

- all
- just color
- parameters except color
- single parameters

Visualizer also supports control of scratches, dirt, snow, wetness and wetness mask.
This can be toggled via icons in global properties of shader. It will set selected parameter for all material, if single
material need to be controlled it can be done via Blender shader. State of mask control is not exported and transferred
to the exported shader