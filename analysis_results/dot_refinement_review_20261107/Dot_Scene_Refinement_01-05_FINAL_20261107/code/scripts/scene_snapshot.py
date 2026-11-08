"""Final-scene snapshot I/O for Blender 5.2.3.

Geometry is constructed from JSON, not appended from a source model. Native
assets contain only material/world/compositor/render context. This is a final
state reconstruction, not a photo-to-model inference or original design history.
"""
import bpy
import json
import re
from pathlib import Path

SCHEMA = 'final-scene-snapshot/1'
ROOT_COLLECTION = '@scene_root'
OBJECT_PROPERTIES = '''location rotation_mode rotation_euler rotation_quaternion rotation_axis_angle scale delta_location delta_rotation_euler delta_rotation_quaternion delta_scale hide_render hide_viewport hide_select display_type display_bounds_type show_bounds show_wire show_all_edges show_transparent show_in_front color visible_camera visible_diffuse visible_glossy visible_transmission visible_volume_scatter visible_shadow is_holdout is_shadow_catcher'''.split()
MESH_PROPERTIES = 'use_auto_texspace texspace_location texspace_size'.split()
SKIP_PROPERTIES = {'rna_type', 'name', 'name_full', 'is_evaluated', 'original', 'users', 'use_fake_user', 'tag', 'is_embedded_data', 'is_library_indirect', 'is_missing', 'session_uid', 'library_weak_reference', 'asset_data', 'override_library', 'animation_data', 'library', 'type', 'active_spline', 'active_material_index', 'active_color_index', 'render_color_index', 'total_vert_sel', 'total_edge_sel', 'total_face_sel', 'is_editmode', 'is_updated', 'is_updated_data', 'is_updated_transform'}

def plain(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, set):
        return sorted(value)
    if hasattr(value, 'to_list'):
        return plain(value.to_list())
    if hasattr(value, 'items'):
        return {k: plain(v) for k, v in value.items()}
    return [plain(v) for v in value]

def clean(value):
    """Remove execution-host paths from descriptive custom metadata only."""
    if isinstance(value, str) and re.search(r"(?:^|[\s\"'])/[^\s/]+/[^\s]+", value):
        return '[local preparation path omitted]'
    if isinstance(value, list):
        return [clean(v) for v in value]
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    return value

def custom(block):
    return clean({k: plain(v) for k, v in block.items() if k != '_RNA_UI'})

def properties(block, names=None):
    out = {}
    for p in block.bl_rna.properties:
        if p.identifier in SKIP_PROPERTIES or p.is_readonly or p.type in {'COLLECTION', 'POINTER'}:
            continue
        if names is not None and p.identifier not in names:
            continue
        out[p.identifier] = plain(getattr(block, p.identifier))
    return out

def apply_properties(block, values):
    # RNA enum flag sets are represented as JSON arrays.
    for key, value in values.items():
        prop = block.bl_rna.properties[key]
        if prop.type == 'ENUM' and prop.is_enum_flag:
            value = set(value)
        if key in {'texspace_location','texspace_size'} and getattr(block,'use_auto_texspace',False):
            continue
        setattr(block, key, value)

def apply_custom(block, values):
    for k, v in values.items():
        block[k] = v

def material_names(data):
    return [m.name if m else None for m in data.materials]

def capture_mesh(m):
    attrs = []
    for a in m.attributes:
        if a.name in {'position', '.edge_verts', '.corner_vert', '.corner_edge'}:
            continue
        if not len(a.data):
            continue
        field = next(p.identifier for p in a.data[0].bl_rna.properties if not p.is_readonly and p.type not in {'POINTER', 'COLLECTION'})
        attrs.append({'name': a.name, 'type': a.data_type, 'domain': a.domain, 'field': field, 'values': [plain(getattr(x, field)) for x in a.data]})
    return {'name': m.name, 'properties': properties(m, MESH_PROPERTIES), 'custom': custom(m),
            'vertices': [list(v.co) for v in m.vertices], 'edges': [list(e.vertices) for e in m.edges],
            'loop_vertex_indices': [l.vertex_index for l in m.loops], 'loop_edge_indices': [l.edge_index for l in m.loops],
            'polygons': [[p.loop_start, p.loop_total] for p in m.polygons], 'attributes': sorted(attrs,key=lambda a:a['name']),
            'materials': material_names(m), 'uv_layers': [{'name': u.name, 'active_render': u.active_render, 'active_clone': u.active_clone} for u in m.uv_layers],
            'active_uv_index': m.uv_layers.active_index}

def capture_curve(c):
    splines = []
    for s in c.splines:
        pts = s.bezier_points if s.type == 'BEZIER' else s.points
        sprops=properties(s)
        if s.type!='NURBS':
            sprops.pop('order_u',None);sprops.pop('order_v',None)
        pprops=[{k:v for k,v in properties(p).items() if k!='weight_softbody'} for p in pts]
        splines.append({'type': s.type, 'properties': sprops, 'points': pprops})
    return {'name': c.name, 'properties': properties(c), 'custom': custom(c), 'splines': splines, 'materials': material_names(c)}

def layer_settings(layer):
    return {'name': layer.name, 'exclude': layer.exclude, 'hide_viewport': layer.hide_viewport,
            'holdout': layer.holdout, 'indirect_only': layer.indirect_only, 'children': [layer_settings(c) for c in layer.children]}

def capture_light_nodes(tree):
    nodes=[]
    for n in tree.nodes:
        if n.bl_idname not in {'ShaderNodeEmission','ShaderNodeOutputLight'}:
            raise RuntimeError('Unsupported light node: '+n.bl_idname)
        nodes.append({'type':n.bl_idname,'name':n.name,'properties':properties(n),
                      'inputs':{str(i):plain(x.default_value) for i,x in enumerate(n.inputs) if hasattr(x,'default_value')}})
    links=[{'from_node':l.from_node.name,'from_socket':list(l.from_node.outputs).index(l.from_socket),
            'to_node':l.to_node.name,'to_socket':list(l.to_node.inputs).index(l.to_socket)} for l in tree.links]
    return {'nodes':nodes,'links':links}

def restore_light_nodes(tree,rec):
    tree.nodes.clear()
    for rn in rec['nodes']:
        n=tree.nodes.new(rn['type']);n.name=rn['name'];apply_properties(n,rn['properties'])
        for i,value in rn['inputs'].items():n.inputs[int(i)].default_value=value
    for l in rec['links']:tree.links.new(tree.nodes[l['from_node']].outputs[l['from_socket']],tree.nodes[l['to_node']].inputs[l['to_socket']])

def shading_fingerprints():
    """Audit native shader graphs without trying to reconstruct them via JSON."""
    import hashlib
    def graph(tree):
        if tree is None:return None
        result={'nodes':[],'links':[]}
        for n in sorted(tree.nodes,key=lambda x:x.name):
            rn={'name':n.name,'type':n.bl_idname,'properties':properties(n),
                'inputs':{str(i):plain(x.default_value) for i,x in enumerate(n.inputs) if hasattr(x,'default_value') and not isinstance(x.default_value,bpy.types.ID)}}
            if hasattr(n,'color_ramp'):
                rn['color_ramp']={'properties':properties(n.color_ramp),'elements':[properties(x) for x in n.color_ramp.elements]}
            if hasattr(n,'texture_mapping'):rn['texture_mapping']=properties(n.texture_mapping)
            if hasattr(n,'color_mapping'):rn['color_mapping']=properties(n.color_mapping)
            result['nodes'].append(rn)
        for l in tree.links:
            result['links'].append([l.from_node.name,list(l.from_node.outputs).index(l.from_socket),l.to_node.name,list(l.to_node.inputs).index(l.to_socket)])
        result['links'].sort();return result
    blocks={}
    for group in ('materials','worlds'):
        for block in getattr(bpy.data,group):blocks[group+'/'+block.name]={'properties':properties(block),'graph':graph(block.node_tree)}
    for image in bpy.data.images:
        blocks['packed_image/'+image.name]={'source':image.source,'size':list(image.size),'packed_sha256':hashlib.sha256(bytes(image.packed_file.data)).hexdigest() if image.packed_file else None}
    scene=bpy.context.scene
    for name in ('view_settings','display_settings','sequencer_colorspace_settings'):
        blocks['scene/'+name]=properties(getattr(scene,name))
    return {name:hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest() for name,value in sorted(blocks.items())}

def capture_scene():
    s = bpy.context.scene
    bpy.context.view_layer.update()
    objects = []
    # Preserve native scene traversal order as well as object values.
    for o in s.objects:
        if o.parent or o.constraints or o.animation_data or o.vertex_groups:
            raise RuntimeError('Unsupported dependency on object: ' + o.name)
        if o.type not in {'MESH', 'CURVE', 'CAMERA', 'LIGHT', 'EMPTY'}:
            raise RuntimeError('Unsupported object type: ' + o.type)
        mods = []
        for m in o.modifiers:
            if m.type not in {'BEVEL', 'WEIGHTED_NORMAL'}:
                raise RuntimeError('Unsupported modifier: '+m.type)
            mods.append({'name': m.name, 'type': m.type, 'properties': properties(m)})
        objects.append({'name':o.name, 'type':o.type, 'data':o.data.name if o.data else None,
                        'properties':properties(o,OBJECT_PROPERTIES), 'custom':custom(o), 'hide_set':o.hide_get(),
                        'collections':[ROOT_COLLECTION if c==s.collection else c.name for c in o.users_collection],
                        'modifiers':mods, 'active_material_index':o.active_material_index,
                        'material_slots':[{'link':sl.link,'material':sl.material.name if sl.material else None} for sl in o.material_slots]})
    meshes = {o.data.name:o.data for o in s.objects if o.type=='MESH'}
    curves = {o.data.name:o.data for o in s.objects if o.type=='CURVE'}
    cameras = {o.data.name:o.data for o in s.objects if o.type=='CAMERA'}
    lights = {o.data.name:o.data for o in s.objects if o.type=='LIGHT'}
    def basic(d):
        result={'name':d.name,'properties':properties(d),'custom':custom(d),'type':d.type}
        for key in ('dof','stereo','cycles'):
            if hasattr(d,key): result[key]=properties(getattr(d,key))
        if hasattr(d,'dof') and d.dof.focus_object:
            raise RuntimeError('Unsupported camera focus object')
        if hasattr(d,'use_nodes') and d.use_nodes:
            result['nodes'] = capture_light_nodes(d.node_tree)
        return result
    collections = [{'name':c.name, 'properties':properties(c), 'custom':custom(c), 'children':[x.name for x in c.children]} for c in sorted(bpy.data.collections,key=lambda c:c.name)]
    return {'schema':SCHEMA,'blender_version':bpy.app.version_string,'scene_name':s.name,
            'scene_custom':custom(s),'active_camera':s.camera.name if s.camera else None,
            'root_collection_custom':custom(s.collection),'root_collections':[c.name for c in s.collection.children],
            'collections':collections,'view_layers':{v.name:layer_settings(v.layer_collection) for v in s.view_layers},
            'meshes':[capture_mesh(m) for _,m in sorted(meshes.items())], 'curves':[capture_curve(c) for _,c in sorted(curves.items())],
            'cameras':[basic(c) for _,c in sorted(cameras.items())],'lights':[basic(c) for _,c in sorted(lights.items())], 'objects':objects,
            'material_names':sorted(m.name for m in bpy.data.materials)}

def clear_geometry():
    for o in list(bpy.data.objects): bpy.data.objects.remove(o,do_unlink=True)
    for name in ('meshes','curves','cameras','lights','collections'):
        group=getattr(bpy.data,name)
        for d in list(group): group.remove(d)

def build_mesh(rec):
    m=bpy.data.meshes.new(rec['name'])
    m.vertices.add(len(rec['vertices']));m.vertices.foreach_set('co',[x for v in rec['vertices'] for x in v])
    m.edges.add(len(rec['edges']));m.edges.foreach_set('vertices',[x for e in rec['edges'] for x in e])
    m.loops.add(len(rec['loop_vertex_indices']));m.loops.foreach_set('vertex_index',rec['loop_vertex_indices']);m.loops.foreach_set('edge_index',rec['loop_edge_indices'])
    m.polygons.add(len(rec['polygons']));m.polygons.foreach_set('loop_start',[p[0] for p in rec['polygons']]);m.polygons.foreach_set('loop_total',[p[1] for p in rec['polygons']])
    for rec_a in rec['attributes']:
        a=m.attributes.get(rec_a['name']) or m.attributes.new(rec_a['name'],rec_a['type'],rec_a['domain'])
        values=rec_a['values']
        flat=[x for value in values for x in value] if isinstance(values[0],list) else values
        a.data.foreach_set(rec_a['field'],flat)
    for name in rec['materials']:m.materials.append(bpy.data.materials[name] if name else None)
    for u in rec['uv_layers']:
        layer=m.uv_layers[u['name']];layer.active_render=u['active_render'];layer.active_clone=u['active_clone']
    if len(m.uv_layers): m.uv_layers.active_index=rec['active_uv_index']
    m.update();apply_properties(m,rec['properties']);apply_custom(m,rec['custom'])
    return m

def build_curve(rec):
    c=bpy.data.curves.new(rec['name'],'CURVE');apply_properties(c,rec['properties']);apply_custom(c,rec['custom'])
    for rs in rec['splines']:
        s=c.splines.new(rs['type']);points=s.bezier_points if s.type=='BEZIER' else s.points;points.add(len(rs['points'])-1)
        apply_properties(s,rs['properties'])
        for p,rp in zip(points,rs['points']):apply_properties(p,rp)
    for name in rec['materials']:c.materials.append(bpy.data.materials[name] if name else None)
    return c

def restore_layers(layer,rec):
    for key in ('exclude','hide_viewport','holdout','indirect_only'):setattr(layer,key,rec[key])
    for child in rec['children']:restore_layers(layer.children[child['name']],child)

def rebuild(snapshot):
    if snapshot['schema']!=SCHEMA:raise ValueError('Unsupported snapshot schema')
    s=bpy.context.scene;clear_geometry()
    apply_custom(s,snapshot['scene_custom']);apply_custom(s.collection,snapshot['root_collection_custom'])
    cols={ROOT_COLLECTION:s.collection}
    for rc in snapshot['collections']:
        c=bpy.data.collections.new(rc['name']);apply_properties(c,rc['properties']);apply_custom(c,rc['custom']);cols[c.name]=c
    for rc in snapshot['collections']:
        for name in rc['children']:cols[rc['name']].children.link(cols[name])
    for name in snapshot['root_collections']:s.collection.children.link(cols[name])
    data={}
    for rec in snapshot['meshes']:data[('MESH',rec['name'])]=build_mesh(rec)
    for rec in snapshot['curves']:data[('CURVE',rec['name'])]=build_curve(rec)
    for group,typ in (('cameras','CAMERA'),('lights','LIGHT')):
        for rec in snapshot[group]:
            d=bpy.data.cameras.new(rec['name']) if typ=='CAMERA' else bpy.data.lights.new(rec['name'],rec['type'])
            d.type=rec['type'];apply_properties(d,rec['properties']);apply_custom(d,rec['custom'])
            for key in ('dof','stereo','cycles'):
                if key in rec:apply_properties(getattr(d,key),rec[key])
            if 'nodes' in rec:restore_light_nodes(d.node_tree,rec['nodes'])
            data[(typ,rec['name'])]=d
    for ro in snapshot['objects']:
        o=bpy.data.objects.new(ro['name'],data.get((ro['type'],ro['data'])))
        for name in ro['collections']:cols[name].objects.link(o)
        apply_properties(o,ro['properties']);apply_custom(o,ro['custom']);o.hide_set(ro['hide_set'])
        for rm in ro['modifiers']:
            m=o.modifiers.new(rm['name'],rm['type']);apply_properties(m,rm['properties'])
        for sl,rs in zip(o.material_slots,ro['material_slots']):
            sl.link=rs['link'];sl.material=bpy.data.materials[rs['material']] if rs['material'] else None
        o.active_material_index=ro['active_material_index']
    s.camera=bpy.data.objects.get(snapshot['active_camera'])
    for name,rec in snapshot['view_layers'].items():restore_layers(s.view_layers[name].layer_collection,rec)
    bpy.context.view_layer.update()

def differences(expected,actual,path='',tol=1e-6):
    """Deep comparison, tolerating only sub-micrometer floating-point roundoff."""
    out=[]
    if isinstance(expected,dict) and isinstance(actual,dict):
        for k in sorted(set(expected)|set(actual)):
            if k not in expected or k not in actual:out.append(path+'/'+k+': missing key')
            else:out.extend(differences(expected[k],actual[k],path+'/'+k,tol))
    elif isinstance(expected,list) and isinstance(actual,list):
        if len(expected)!=len(actual):out.append(path+': length mismatch')
        else:
            for i,(a,b) in enumerate(zip(expected,actual)):out.extend(differences(a,b,path+'/'+str(i),tol))
    elif isinstance(expected,(int,float)) and not isinstance(expected,bool) and isinstance(actual,(int,float)):
        if abs(expected-actual)>tol:out.append(path+f': {expected} != {actual}')
    elif expected!=actual:out.append(path+f': {expected!r} != {actual!r}')
    return out
