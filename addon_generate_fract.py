import bpy
from mathutils import Vector, Euler


bl_info = {
    "name": "Generate Fractal",
    "author": "Kryštof Ježek",
    "version": (1, 0, 9),
    "blender": (2, 80, 0),
    "location": "View3D > Add > Generate Fractal from object",
    "description": "Fractalizes the selected object",
    "warning": "",
    "wiki_url": "",
    "category": "Generate",
}


class FractalSegmentItem(bpy.types.PropertyGroup):
    """Class holding information about a specific fractal segment"""
    scale_change: bpy.props.FloatProperty(name="Scale", default=0.5)
    location_change: bpy.props.FloatVectorProperty(
        name="Direction",
        unit="NONE",
        size=3,
        default=(0, 0, 0)
    )
    # TODO: implement location_lerp
    location_lerp: bpy.props.FloatProperty(name="Translation", default=0.5)
    rotation_change: bpy.props.FloatVectorProperty(
        name="Rotation",
        unit="ROTATION",
        size=3,
        default=(0, 0, 0)
    )

    def __repr__(self):
        return "FractalSegmentItem()"

    def __str__(self):
        return str((self.scale_change,
                    self.location_change,
                    self.location_lerp,
                    self.rotation_change))


class FractalLayerItem(bpy.types.PropertyGroup):
    """A layer that holds several segments"""
    layer_segments: bpy.props.CollectionProperty(type=FractalSegmentItem)


class UIListActions(bpy.types.Operator):
    bl_idname = "custom.generate_fractal_list_action"
    bl_label = "internal Fractalizator operator"

    action: bpy.props.EnumProperty(
        items=(
            ('REMOVE', "Remove Layer", ""),
            ('ADD', "Add Layer", ""),
            ('SREMOVE', "Remove Segment", ""),
            ('SADD', "Add Segment", "")
        )
    )

    index: bpy.props.IntProperty(min=0, default=0)
    segment_index: bpy.props.IntProperty(min=0, default=0)

    def invoke(self, context, event):
        scn = context.scene

        if len(scn.fractal_layers) - 1 >= self.index >= 0 and self.action == 'REMOVE':
            # TODO: change this to remove selected layer instead
            scn.fractal_layers.remove(len(scn.fractal_layers) - 1)
        elif self.action == 'ADD':
            scn.fractal_layers.add()
        elif len(scn.fractal_layers) - 1 >= self.index >= 0 and len(scn.fractal_layers[
                                                                        self.index].layer_segments) - 1 >= self.segment_index >= 0 and self.action == 'SREMOVE':
            scn.fractal_layers[self.index].layer_segments.remove(self.segment_index)
        elif len(scn.fractal_layers) - 1 >= self.index >= 0 and self.action == 'SADD':
            scn.fractal_layers[self.index].layer_segments.add()

        return {"FINISHED"}


class POPUP_UL_generate_fractals(bpy.types.UIList):
    """Custom drawer for fractal layers and segments"""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        col = layout.column()
        row = col.row()
        row.label(text="Layer " + str(index))
        add_segment_button = row.operator("custom.generate_fractal_list_action", icon='ADD', text="Add segment")
        add_segment_button.action = 'SADD'
        add_segment_button.index = index
        for i in range(len(context.scene.fractal_layers[index].layer_segments)):
            row = col.row(align=True)
            column = row.column()
            column.label(text="Segment " + str(i))
            segment = context.scene.fractal_layers[index].layer_segments[i]
            subrow = column.row()
            subrow.prop(segment, "location_change")
            subrow = column.row()
            subrow.prop(segment, "rotation_change")
            subrow = column.row()
            subrow.prop(segment, "scale_change")
            subrow.prop(segment, "location_lerp")
            remove_segment_button = row.operator("custom.generate_fractal_list_action", icon='PANEL_CLOSE', text="")
            remove_segment_button.action = 'SREMOVE'
            remove_segment_button.index = index
            remove_segment_button.segment_index = i

    def invoke(self, context, event):
        pass


def gen_layer(self, root, object, layers, current_rotation, depth):
    """
    Generate fractals recursively
    Parameters
    ----------
    self : GenerateFractal
        The plugin instance.
    root : Blender Object
        The original object we want to fractalize.
    object : Blender Object
        The current object we want to duplicate in this layer.
    layers : bpy.props.CollectionProperty(type=FractalLayerItem)
        Collection of layers.
    current_rotation : Euler
        Rotation of the current layer and segment.
    depth : int
        The current depth.
    """

    # Nothing left to do
    if (depth <= 0):
        return

    # Segment id is held just for naming objects
    segment_id = 0

    for segment in layers[(len(layers) - (depth - self.depth)) % len(layers)].layer_segments:
        new_object = object.copy()
        new_object.data = object.data.copy()
        self.view_layer.active_layer_collection.collection.objects.link(new_object)
        new_object.name = "Level" + str(depth) + ":" + str(segment_id)
        self.view_layer.update()
        self.view_layer.objects.active = new_object
        new_object.select_set(True)
        new_object.scale = new_object.scale * (segment.scale_change)
        self.view_layer.update()
        rot = current_rotation.to_matrix()
        rot.invert()
        new_object.rotation_euler.rotate(Euler(segment.rotation_change))
        local_direction = (Vector(segment.location_change) @ rot).normalized()
        result, location, normal, index = new_object.ray_cast(origin=Vector((0, 0, 0)), direction=local_direction)
        if result:
            new_object.location += location
        else:
            # Whoops, looks like pivot isn't inside of the object
            print("WARNING: Raycast hasn't hit anything. Make sure segment Direction points towards mesh.")
            continue;
        self.view_layer.update()
        segment_rotation = current_rotation.copy()
        segment_rotation.rotate(Euler(segment.rotation_change))

        bpy.ops.object.transform_apply(location=False, scale=True, rotation=True)
        new_object.select_set(False)

        segment_id += 1

        gen_layer(self, root, new_object, layers, segment_rotation, depth - 1)


class GenerateFractal(bpy.types.Operator):
    """Fractalizes an object"""
    bl_idname = "object.generate_fractal"
    bl_label = "Generate Fractal"

    depth: bpy.props.IntProperty(name="Depth", default=4, min=1, soft_max=8)
    index: bpy.props.IntProperty(name="layerIndex", default=0)

    def __init__(self):
        self.view_layer = None

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        self.view_layer = bpy.context.view_layer
        if len(context.scene.fractal_layers) <= 0 or False in [(len(layer.layer_segments) > 0) for layer in
                                                               context.scene.fractal_layers]:
            print("WARNING: Tried generating fractal with no layers or segments!")
            return {"CANCELLED"}
        gen_layer(self, context.active_object, context.active_object, context.scene.fractal_layers, context.active_object.rotation_euler,
                  self.depth)
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        col = layout.column()
        col.prop(self, "depth")
        row = col.row()
        row.label(text="Layers")
        row.label(text=str(len(scene.fractal_layers)))

        col = layout.column()

        col.template_list(
            "POPUP_UL_generate_fractals",
            "",
            scene,
            "fractal_layers",
            self,
            "index",
            rows=2
        )

        row = col.row(align=True)
        add_layer_button = row.operator(
            "custom.generate_fractal_list_action",
            icon='ADD',
            text="Add layer"
        )
        add_layer_button.action = 'ADD'
        add_layer_button.index = 0
        remove_layer_button = row.operator(
            "custom.generate_fractal_list_action",
            icon='REMOVE',
            text="Remove last layer"
        )
        remove_layer_button.action = 'REMOVE'
        remove_layer_button.index = 0


# Registration
def gen_fract_button(self, context):
    self.layout.operator(
        GenerateFractal.bl_idname,
        text="Generate fractal from selected",
        icon='PLUGIN')


def register():
    bpy.utils.register_class(FractalSegmentItem)
    bpy.utils.register_class(FractalLayerItem)
    bpy.utils.register_class(UIListActions)
    bpy.utils.register_class(POPUP_UL_generate_fractals)
    bpy.utils.register_class(GenerateFractal)
    bpy.types.Scene.fractal_layers = bpy.props.CollectionProperty(
        type=FractalLayerItem)
    bpy.types.VIEW3D_MT_add.append(gen_fract_button)


def unregister():
    bpy.utils.unregister_class(GenerateFractal)
    bpy.utils.unregister_class(POPUP_UL_generate_fractals)
    bpy.utils.unregister_class(UIListActions)
    bpy.utils.unregister_class(FractalLayerItem)
    bpy.utils.unregister_class(FractalSegmentItem)


if __name__ == "__main__":
    register()
