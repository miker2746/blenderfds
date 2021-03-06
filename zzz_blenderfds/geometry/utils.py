"""BlenderFDS, geometric utilities."""

import bpy, bmesh

### Working on Blender objects

def object_get_global_copy(context, ob, suffix='_tmp'):
    """Copy object, apply modifiers, apply transformations."""
    me_tmp = ob.to_mesh(
        scene=context.scene,
        apply_modifiers=True,
        settings="RENDER",
        calc_tessface=True,
        calc_undeformed=False,
    )
    me_tmp.transform(ob.matrix_world)
    ob_tmp = bpy.data.objects.new(ob.name + suffix, me_tmp)
    context.scene.objects.link(ob_tmp)  # always link to prevent a bug
    return ob_tmp

def get_global_mesh(context, ob) -> "Mesh":
    """Return object mesh modified and transformed in global coordinates."""
    me = ob.to_mesh(scene=context.scene, apply_modifiers=True, settings="RENDER") # apply modifiers (as in RENDER, not PREVIEW)
    me.transform(ob.matrix_world) # transform mesh in global coordinates, apply scale, rotation, and location
    return me

def set_global_mesh(context, ob, me) -> "None":
    """Set object mesh from mesh in global coordinates."""
    try: me.transform(ob.matrix_world.inverted()) # transform global mesh to local coordinates, apply scale, rotation, and location
    except ValueError: pass
    ob.data = me

def get_new_object(context, scene, name, me=None, linked=True) -> "Object":
    """Create new object, named name, set mesh me if any, link to scene."""
    if not me: me = bpy.data.meshes.new("mesh") # dummy mesh
    ob = bpy.data.objects.new(name, me)
    if linked: scene.objects.link(ob)
    return ob

def get_object_by_name(context, name) -> "Object or None":
    """Get an object by name and return it"""
    if name and name in bpy.data.objects: return bpy.data.objects[name]

### Working on Blender materials

def get_new_material(context, name) -> "Material":
    """Create new material, named name."""
    return bpy.data.materials.new(name)

def get_material_by_name(context, name) -> "Material or None":
    """Get a material by name and return it"""
    if name and name in bpy.data.materials: return bpy.data.materials[name]

def get_material(context, name) -> "Material or None":
    """Get an existing material by name or create a new one, and return it"""
    if name and name in bpy.data.materials: return bpy.data.materials[name]
    return bpy.data.materials.new(name)

### Working on Blender meshes

def get_tessfaces(context, me) -> "Mesh tessfaces":
    """Get bmesh tessfaces."""
    me.update(calc_tessface=True)
    return me.tessfaces

def insert_vertices_into_mesh(me, verts) -> "None":  # FIXME not used
    """Insert vertices into mesh."""
    bm = bmesh.new()
    bm.from_mesh(me) # Inject me into bm
    for v in verts: bm.verts.new(v) # Add vertices
    bm.to_mesh(me) # Inject bm into me
    bm.free()

### Working on bounding box and size

def get_global_bbox(context, ob) -> "x0, x1, y0, y1, z0, z1":
    """Get object’s bounding box in global coordinates and in xbs format."""
    # Init
    ob_tmp = get_new_object(context, context.scene, "tmp", get_global_mesh(context, ob), linked=False)
    # Calc the bounding box in global coordinates, as it's global
    bbox = get_bbox(ob_tmp)
    # Clean up temporary object
    bpy.data.objects.remove(ob_tmp, do_unlink=True)
    # Return
    return bbox

def get_bbox(ob) -> "x0, x1, y0, y1, z0, z1":
    """Get object’s bounding box in xbs format from an object."""
    bb = ob.bound_box
    return bb[0][0], bb[6][0], bb[0][1], bb[6][1], bb[0][2], bb[6][2]

def calc_movement_from_bbox1_to_bbox0(bbox0, bbox1) -> "mx, my, mz":  # FIXME not used
    """Calc movement from bbox1 to bbox0 (bounding boxes in xb format)."""
    return (
        (bbox0[0] + bbox0[1] - bbox1[0] - bbox1[1]) / 2., # (bb0minx + bb0maxx) / 2. - (bb1minx + bb1maxx) / 2.
        (bbox0[2] + bbox0[3] - bbox1[2] - bbox1[3]) / 2., # (bb0miny + bb0maxy) / 2. - (bb1miny + bb1maxy) / 2.
        (bbox0[4] + bbox0[5] - bbox1[4] - bbox1[5]) / 2., # (bb0minz + bb0maxz) / 2. - (bb1minz + bb1maxz) / 2.
    )

def get_global_dimensions(context, ob) -> "dx, dy, dz":
    """Get object dimensions in global coordinates."""
    x0, x1, y0, y1, z0, z1 = get_global_bbox(context, ob)
    return abs(x1-x0), abs(y1-y0), abs(z1-z0)

def get_global_area(context, ob) -> "Float":
    """Get area of object in global coordinates."""
    area = 0.
    me_tmp = get_global_mesh(context, ob) # Apply modifiers and scales
    for polygon in me_tmp.polygons: area += polygon.area
    bpy.data.meshes.remove(me_tmp, do_unlink=True)
    return area

### Working on position

def set_balanced_center_position(context, ob) -> "None":
    """Set object center position"""
    if context.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    # origin_set works on currently selected objects
    # unselect all, select ob, set origin, and try to revert selections to original
    active_ob = context.active_object
    bpy.ops.object.select_all(action='DESELECT')
    ob.select = True
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY')
    if active_ob: active_ob.select = True

def move_xbs(xbs, movement) -> "None":  # FIXME not used
    """Move xbs of movement vector."""
    for xb in xbs: xb[:] = xb[0]+movement[0], xb[1]+movement[0], xb[2]+movement[1], xb[3]+movement[1], xb[4]+movement[2], xb[5]+movement[2]
