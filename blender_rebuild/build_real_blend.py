import argparse, hashlib, json, math, sys
from pathlib import Path
import bpy
from mathutils import Vector


def args():
    a=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True); p.add_argument('--roundtrip',required=True)
    p.add_argument('--manifest',required=True); p.add_argument('--preview',required=True)
    return p.parse_args(a)


def clear():
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    for blocks in (bpy.data.meshes,bpy.data.curves,bpy.data.materials,bpy.data.cameras,bpy.data.lights):
        for b in list(blocks):
            if b.users==0: blocks.remove(b)


def mat(name,color,metal=0.0,rough=.5,trans=0.0):
    m=bpy.data.materials.new(name); m.use_nodes=True
    bs=m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value=(*color,1)
    bs.inputs['Metallic'].default_value=metal; bs.inputs['Roughness'].default_value=rough
    if bs.inputs.get('Transmission Weight'): bs.inputs['Transmission Weight'].default_value=trans
    if bs.inputs.get('Coat Weight'): bs.inputs['Coat Weight'].default_value=.35 if 'BODY' in name else 0
    return m


def empty(name,loc=(0,0,0),parent=None):
    o=bpy.data.objects.new(name,None); bpy.context.scene.collection.objects.link(o)
    o.location=loc; o.parent=parent; return o


def finish(obj,name,material,parent=None,bevel=.0):
    obj.name=name; obj.data.name=name+'_MESH'; obj.parent=parent
    if material: obj.data.materials.append(material)
    for p in obj.data.polygons: p.use_smooth=True
    if bevel:
        mod=obj.modifiers.new('NH_Bevel','BEVEL'); mod.width=bevel; mod.segments=2; mod.limit_method='ANGLE'
    obj['nomadhub_semantic_node']=name
    return obj


def box(name,dims,loc,material,parent=None,rot=(0,0,0),bevel=.02):
    bpy.ops.mesh.primitive_cube_add(location=loc,rotation=rot); o=bpy.context.object
    o.dimensions=dims; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return finish(o,name,material,parent,bevel)


def child_box(name,dims,loc,material,parent,bevel=.012):
    o=box(name,dims,(0,0,0),material,None,bevel=bevel); o.parent=parent; o.location=loc; return o


def profile_prism(name,profile,width,material,parent):
    y=width/2; verts=[(x,-y,z) for x,z in profile]+[(x,y,z) for x,z in profile]; n=len(profile)
    faces=[]; faces.append(tuple(range(n-1,-1,-1))); faces.append(tuple(range(n,2*n)))
    for i in range(n):
        j=(i+1)%n; faces.append((i,j,n+j,n+i))
    mesh=bpy.data.meshes.new(name+'_MESH'); mesh.from_pydata(verts,[],faces); mesh.update()
    o=bpy.data.objects.new(name,mesh); bpy.context.scene.collection.objects.link(o)
    return finish(o,name,material,parent,.025)


def wheel(name,loc,parent,bodymat,rubber):
    root=empty(name+'_ROOT',loc,parent)
    bpy.ops.mesh.primitive_torus_add(major_radius=.31,minor_radius=.105,major_segments=32,minor_segments=12,rotation=(math.pi/2,0,0))
    tire=finish(bpy.context.object,name+'_TIRE',rubber,root,.005); tire.location=(0,0,0)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=.245,depth=.12,rotation=(math.pi/2,0,0))
    rim=finish(bpy.context.object,name+'_RIM',bodymat,root,.004); rim.location=(0,0,0)
    return root


def animate(root,axis,angle):
    root.rotation_mode='XYZ'
    for f,v in ((1,0),(48,angle),(96,0)):
        root.rotation_euler[axis]=v; root.keyframe_insert('rotation_euler',index=axis,frame=f)


def look_at(obj,target):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()


def main():
    a=args(); clear(); sc=bpy.context.scene
    sc.unit_settings.system='METRIC'; sc.unit_settings.length_unit='METERS'; sc.unit_settings.scale_length=1
    sc.frame_start=1; sc.frame_end=120; sc.render.fps=30
    silver=mat('MAT_BODY_SILVER',(.72,.76,.80),.18,.25); dark=mat('MAT_TRIM',(.04,.05,.06),.05,.32)
    glass=mat('MAT_GLASS',(.025,.07,.11),0,.12,.65); rubber=mat('MAT_RUBBER',(.015,.018,.02),0,.86)
    cyan=mat('MAT_ACCENT_CYAN',(0,.58,.65),.1,.28); red=mat('MAT_TAILLIGHT',(.55,.02,.01),.05,.25)
    root=empty('RV_ROOT'); body=empty('BODY',parent=root); gcol=empty('GLASS',parent=root); doors=empty('DOORS',parent=root)
    hatches=empty('HATCHES',parent=root); wheels=empty('WHEELS',parent=root); roof=empty('ROOF',parent=root)
    lights=empty('LIGHTS',parent=root); mirrors=empty('MIRRORS',parent=root)
    box('BODY_MAIN',(7.05,2.30,2.35),(0.80,0,1.48),silver,body,bevel=.06)
    profile=[(-4.43,.35),(-4.38,1.15),(-4.08,2.20),(-3.62,2.76),(-2.60,2.76),(-2.60,.35)]
    profile_prism('BODY_CAB',profile,2.26,silver,body)
    box('FRONT_BUMPER',(.16,1.78,.23),(-4.46,0,.44),dark,body,bevel=.06)
    box('REAR_BUMPER',(.16,1.82,.23),(4.43,0,.44),dark,body,bevel=.06)
    box('SIDE_SKIRT_L',(7.1,.10,.18),(.45,-1.15,.43),dark,body,bevel=.03)
    box('SIDE_SKIRT_R',(7.1,.10,.18),(.45,1.15,.43),dark,body,bevel=.03)
    box('GLASS_WINDSHIELD',(.055,1.92,.88),(-4.09,0,2.18),glass,gcol,rot=(0,-math.radians(17),0),bevel=.035)
    for side,suf in ((-1,'L'),(1,'R')):
        box('GLASS_CAB_'+suf,(1.0,.035,.72),(-3.48,side*1.145,2.02),glass,gcol,bevel=.04)
        for i,(x,w) in enumerate(((-1.75,1.05),(-.35,1.05),(1.45,1.30),(3.10,.90)),1):
            box(f'GLASS_LIVING_{suf}_{i:02}',(w,.035,.68),(x,side*1.165,2.08),glass,gcol,bevel=.045)
    box('GLASS_REAR',(.035,1.35,.65),(4.47,0,1.98),glass,gcol,bevel=.04)
    specs=[('DOOR_DRIVER_L_ROOT',(-4.02,-1.18,.45),(0.82,.05,1.72),(.41,0,.86),-68),('DOOR_PASSENGER_R_ROOT',(-4.02,1.18,.45),(0.82,.05,1.72),(.41,0,.86),68),('DOOR_LIVING_R_ROOT',(-.82,1.18,.34),(.78,.05,1.96),(.39,0,.98),82)]
    for n,loc,dims,local,deg in specs:
        r=empty(n,loc,doors); child_box(n.replace('_ROOT',''),dims,local,silver,r); animate(r,2,math.radians(deg))
    for side,suf,sgn in ((-1,'L',-1),(1,'R',1)):
        for i,x in enumerate((-1.95,.35,2.78),1):
            r=empty(f'HATCH_{suf}_{i}_ROOT',(x,side*1.18,.92),hatches)
            child_box(f'HATCH_{suf}_{i}',(1.05,.045,.55),(0,0,-.275),silver,r); animate(r,0,math.radians(70*sgn))
    for n,x,y in (('WHEEL_FL',-3.245,-1.06),('WHEEL_FR',-3.245,1.06),('WHEEL_RL',1.905,-1.06),('WHEEL_RR',1.905,1.06)):
        r=wheel(n,(x,y,.43),wheels,silver,rubber)
        r.rotation_mode='XYZ'; r.rotation_euler[1]=0; r.keyframe_insert('rotation_euler',index=1,frame=1); r.rotation_euler[1]=math.radians(720); r.keyframe_insert('rotation_euler',index=1,frame=120)
    box('ROOF_AC',(.95,.78,.24),(-2.05,0,2.91),silver,roof,bevel=.08)
    box('SOLAR_ARRAY',(2.45,1.55,.06),(.05,0,2.82),dark,roof,bevel=.01)
    box('ROOF_SKYLIGHT',(.65,.55,.10),(1.70,0,2.86),glass,roof,bevel=.04)
    box('AWNING_R',(4.7,.14,.16),(.40,1.18,2.68),dark,roof,bevel=.05)
    box('FRONT_GRILLE',(.045,1.28,.52),(-4.49,0,.92),dark,lights,bevel=.05)
    for y in (-.73,.73): box('HEADLIGHT_'+('L' if y<0 else 'R'),(.05,.36,.20),(-4.50,y,1.30),cyan,lights,bevel=.06)
    for y in (-.78,.78): box('TAILLIGHT_'+('L' if y<0 else 'R'),(.05,.22,.60),(4.50,y,1.18),red,lights,bevel=.05)
    for side,suf in ((-1,'L'),(1,'R')):
        mr=empty('MIRROR_'+suf+'_ROOT',(-3.82,side*1.18,1.82),mirrors)
        child_box('MIRROR_'+suf+'_HOUSING',(.25,.23,.30),(-.10,side*.19,.02),silver,mr,.04)
        child_box('MIRROR_'+suf+'_GLASS',(.12,.025,.20),(-.13,side*.31,.02),glass,mr,.02)
    box('ACCENT_L',(4.8,.018,.07),(.35,-1.185,1.15),cyan,body,rot=(0,math.radians(-2),0),bevel=.01)
    box('ACCENT_R',(4.8,.018,.07),(.35,1.185,1.15),cyan,body,rot=(0,math.radians(-2),0),bevel=.01)
    cam_data=bpy.data.cameras.new('Camera'); cam=bpy.data.objects.new('Camera',cam_data); sc.collection.objects.link(cam); sc.camera=cam
    cam.location=(-11,-10,7.2); look_at(cam,(0,0,1.35)); cam.data.lens=55
    for name,loc,energy,size in [('Key',(-5,-6,9),1800,5),('Fill',(4,-2,6),1100,4),('Rim',(2,7,8),1300,4)]:
        ld=bpy.data.lights.new(name,'AREA'); ld.energy=energy; ld.shape='DISK'; ld.size=size
        lo=bpy.data.objects.new(name,ld); sc.collection.objects.link(lo); lo.location=loc; look_at(lo,(0,0,1.3))
    sc.render.engine='BLENDER_EEVEE_NEXT'; sc.render.resolution_x=1280; sc.render.resolution_y=720; sc.render.resolution_percentage=100
    sc.render.image_settings.file_format='PNG'; sc.render.filepath=a.preview; sc.world.color=(.035,.045,.06)
    sc['nomadhub_project']='NomadHub General3'; sc['nomadhub_version']='V1.7'; sc['build_type']='BLENDER_NATIVE_REBUILD'
    Path(a.output).parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=a.output,compress=True)
    bpy.ops.render.render(write_still=True)
    bpy.ops.export_scene.gltf(filepath=a.roundtrip,export_format='GLB',export_animations=True,export_apply=True)
    bpy.ops.wm.save_as_mainfile(filepath=a.output,compress=True)
    payload={'artifact_type':'genuine_blender_native_project','blender_version':bpy.app.version_string,'blend':a.output,'blend_bytes':Path(a.output).stat().st_size,'blend_sha256':hashlib.sha256(Path(a.output).read_bytes()).hexdigest(),'roundtrip_glb':a.roundtrip,'roundtrip_sha256':hashlib.sha256(Path(a.roundtrip).read_bytes()).hexdigest(),'preview':a.preview,'objects':len(bpy.data.objects),'meshes':len(bpy.data.meshes),'materials':len(bpy.data.materials),'actions':len(bpy.data.actions),'units':'meters','scope_note':'Genuine Blender-saved editable baseline generated with Blender-native objects, modifiers and keyframes; not yet hand-retopologized production surfacing.'}
    Path(a.manifest).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print('NOMADHUB_NATIVE_BLEND_OK'); print(json.dumps(payload,ensure_ascii=False))

if __name__=='__main__': main()
