import bpy
import gpu
from gpu_extras.batch import batch_for_shader 

class MotionPathPoint(bpy.types.PropertyGroup):
    frame: bpy.props.IntProperty()
    location: bpy.props.FloatVectorProperty(size=3)

# to be attached to each bone
class MotionPathData(bpy.types.PropertyGroup):
    points: bpy.props.CollectionProperty(type=MotionPathPoint)
    # start and end of cached frames
    start_frame: bpy.props.IntProperty(default=1)
    end_frame: bpy.props.IntProperty(default=256)
    
# attached to the scene - global
class AnimSketcherSettings(bpy.types.PropertyGroup):
    timeline_width: bpy.props.IntProperty(default=32)
    view_start_frame: bpy.props.IntProperty(default=1, min=0)
    view_end_frame:bpy.props.IntProperty(default=256, min=0)
    sketch_points: bpy.props.CollectionProperty(type=MotionPathPoint)


def draw_callback_px(self, context):
    scene = context.scene
    anim_sketcher = scene.anim_sketcher
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    gpu.state.line_width_set(2.0)
    batch = batch_for_shader(
        shader, 
        'LINE_STRIP', 
        {"pos": [p.location for p in 
            context.active_bone.cached_motion_path.points[
                anim_sketcher.view_start_frame - scene.frame_start : anim_sketcher.view_end_frame + 1 - scene.frame_start
            ]
        ]}
    )
    shader.uniform_float("color", (1.0, 0.0, 0.0, 1.0))
    batch.draw(shader)
    
    # restore defaults
    gpu.state.line_width_set(1.0)


class GetMotionDataOperator(bpy.types.Operator):
    bl_idname = "view3d.get_motion_data"
    bl_label = "Print motion data of the selected bone"
    
    def invoke(self, context, event):
        
        if context.area.type == 'VIEW_3D':
            active_bone = bpy.context.active_pose_bone
            bones = bpy.context.selected_pose_bones
            
            arm = bpy.context.active_object
            
            scene = bpy.context.scene
            
            if not active_bone:
                self.report({'WARNING'}, "No pose bone selected, cannot run operator")
                return {'CANCELLED'}
            
            # dependency graph
            depsgraph = bpy.context.evaluated_depsgraph_get()
            
            self.current_frame = bpy.context.scene.frame_current
            
            #path = []
            active_bone.bone.cached_motion_path.points.clear()

            for frame in range(scene.frame_start, scene.frame_end + 1):
                scene.frame_set(frame)
                depsgraph.update()
            
                eval_arm = arm.evaluated_get(depsgraph)
                eval_bone = eval_arm.pose.bones[active_bone.name]
                
                # multiply local object space and local bone space
                bone_world_matrix = eval_arm.matrix_world @ eval_bone.matrix
                location = bone_world_matrix.translation
                #print("Frame: ", frame, " Location: ", location)
                #bpy.ops.mesh.primitive_cube_add(location=location, scale=(0.1, 0.1, 0.1))
                #path += [location]
                p = active_bone.bone.cached_motion_path.points.add()
                p.frame = frame
                p.location = location
            
            scene.anim_sketcher.timeline_width = (scene.frame_end - scene.frame_start + 1) // 2
            
            args = (self, context)
            self._handle = bpy.types.SpaceView3D.draw_handler_add(draw_callback_px, args, 'WINDOW', 'POST_VIEW')    
                
            scene.frame_set(self.current_frame)
            
            bpy.context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        
        else:
            self.report({'WARNING'}, "View3D not found, cannot run operator")
            return {'CANCELLED'}
    
    
    def modal(self, context, event):
        context.area.tag_redraw()
        scene = context.scene
        active_bone = context.active_pose_bone
        
        if scene.frame_current != self.current_frame:
            self.current_frame = scene.frame_current
            
            scene.anim_sketcher.view_start_frame = max(scene.frame_start, self.current_frame - scene.anim_sketcher.timeline_width)
            scene.anim_sketcher.view_end_frame = min(scene.frame_end, self.current_frame + scene.anim_sketcher.timeline_width)
            return {'RUNNING_MODAL'}
        elif event.type == 'WHEELUPMOUSE':
            #self.start_frame = min(scene.frame_end, self.start_frame + 1)
            scene.anim_sketcher.timeline_width += 1
            scene.anim_sketcher.timeline_width = min(scene.anim_sketcher.timeline_width, (scene.frame_end - scene.frame_start))
            
            scene.anim_sketcher.view_start_frame = max(scene.frame_start, self.current_frame - scene.anim_sketcher.timeline_width)
            scene.anim_sketcher.view_end_frame = min(scene.frame_end, self.current_frame + scene.anim_sketcher.timeline_width)
            return {'RUNNING_MODAL'}
        elif event.type == 'WHEELDOWNMOUSE':
            #self.start_frame = max(scene.frame_start, self.start_frame - 1)
            scene.anim_sketcher.timeline_width -= 1
            scene.anim_sketcher.timeline_width = max(1, scene.anim_sketcher.timeline_width)
            
            scene.anim_sketcher.view_start_frame = max(scene.frame_start, self.current_frame - scene.anim_sketcher.timeline_width)
            scene.anim_sketcher.view_end_frame = min(scene.frame_end, self.current_frame + scene.anim_sketcher.timeline_width)
            return {'RUNNING_MODAL'}
        elif event.type in {'ESC', 'RIGHTMOUSE'}:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'CANCELLED'}



        return {'PASS_THROUGH'}
        
        

def menu_func(self, context):
    self.layout.operator(GetMotionDataOperator.bl_idname, text="Get Motion Data Operator")


# Register and add to the "view" menu (required to also use F3 search "Modal Draw Operator" for quick access).
def register():
    bpy.utils.register_class(MotionPathPoint)
    bpy.utils.register_class(MotionPathData)
    bpy.types.Bone.cached_motion_path = bpy.props.PointerProperty(
        type = MotionPathData
    )
    
    bpy.utils.register_class(AnimSketcherSettings)
    bpy.types.Scene.anim_sketcher = bpy.props.PointerProperty(
        type = AnimSketcherSettings
    )
    
    bpy.utils.register_class(GetMotionDataOperator)
    bpy.types.VIEW3D_MT_view.append(menu_func)


def unregister():
    bpy.utils.unregister_class(GetMotionDataOperator)
    bpy.types.VIEW3D_MT_view.remove(menu_func)

    bpy.utils.unregister_class(AnimSketcherSettings)
    bpy.utils.unregister_class(MotionPathData)
    bpy.utils.unregister_class(MotionPathPoint)

    del bpy.types.Scene.anim_sketcher
    del bpy.types.Bone.cached_motion_path

if __name__ == "__main__":
    register()
