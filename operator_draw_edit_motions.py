import bpy
from bpy_extras import view3d_utils
import gpu
from gpu_extras.batch import batch_for_shader


from mathutils import Vector

def compute_arc_lengths(points):
    lengths = [0.0]
    total = 0.0

    for i in range (1, len(points)):
        seg_total_len = (points[i] - points[i-1]).length
        total += seg_total_len
        lengths.append(total)
    
    return lengths, total

def sample_path_at_t(points, arc_lengths, total_length, t):
    target_len = t * total_length

    for i in range(1, len(points)):
        if arc_lengths[i] >= target_len:
            prev_len = arc_lengths[i-1]
            seg_len = arc_lengths[i] - prev_len
            factor = (target_len - prev_len) / seg_len

            return points[i-1].lerp(points[i], factor)
    return points[-1]  

#def project_to_depth(point, view_dir, target_depth):
#    current_depth = point.dot(view_dir)
#    delta = target_depth - current_depth
#    return point + view_dir * delta

class DrawEditMotionsOperator(bpy.types.Operator):
    bl_idname = "view3d.draw_edit_motions"
    bl_label = "Draw to Edit Motions"

    def invoke(self, context, event):
        #self.points = []
        context.scene.anim_sketcher.sketch_points.clear()
        
        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self.draw_callback,
            (context,),
            'WINDOW',
            'POST_VIEW'
        )

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            # convert 2D mouse to 3D
            region = context.region
            rv3d = context.region_data
            coord = (event.mouse_region_x, event.mouse_region_y)

            world_pos = view3d_utils.region_2d_to_location_3d(
                region,
                rv3d,
                coord,
                rv3d.view_location
            )

            #self.points.append(world_pos)
            sketch_point = context.scene.anim_sketcher.sketch_points.add()
            sketch_point.location = world_pos
            context.area.tag_redraw()
            
        elif event.type == 'LEFTMOUSE':
            rv3d = context.region_data
            view_dir = rv3d.view_rotation @ Vector((0, 0, -1))

            # Line up with active bone
            active_bone = context.active_pose_bone
            motion_path_points = active_bone.bone.cached_motion_path.points
            
            motion_path = [Vector(p.location) for p in motion_path_points]
            mouse_path = [Vector(p.location) for p in context.scene.anim_sketcher.sketch_points]
            
            print("Before: ", mouse_path)
            
            motion_path_lengths, motion_path_total = compute_arc_lengths(motion_path)
            mouse_path_lengths, mouse_path_total = compute_arc_lengths(mouse_path)

            new_mouse_path = []
            
            origin = rv3d.view_matrix.inverted().translation
            
            # TODO: switch to motion_path
            for i, p in enumerate(mouse_path):
                t = mouse_path_lengths[i] / mouse_path_total

                sampled_motion_path = sample_path_at_t(
                    motion_path,
                    motion_path_lengths,
                    motion_path_total,
                    t)
                    
                # prev: match depth
                #target_depth = sampled_motion_path.dot(view_dir)
                #new_p = project_to_depth(p, view_dir, target_depth)
                
                direction = (mouse_path[i] - origin).normalized()
                t_target = (sampled_motion_path - origin).dot(direction)                   
                new_p = origin + direction * t_target
            
                new_mouse_path.append(new_p)
            
            for i in range(len(mouse_path)):
                context.scene.anim_sketcher.sketch_points[i].location = new_mouse_path[i]
            
            print("After: ", mouse_path)
            
            context.area.tag_redraw()
            return {'FINISHED'}
        elif event.type == 'ESC' or event.type == 'RIGHTMOUSE':
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            context.area.tag_redraw()
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def draw_callback(self, context):
        sketch_points = context.scene.anim_sketcher.sketch_points
        if len(sketch_points) < 2:
            return

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": [p.location for p in sketch_points]})
        shader.uniform_float("color", (0, 0, 0, 1))
        batch.draw(shader)
        
def menu_func(self, context):
    self.layout.operator(DrawEditMotionsOperator.bl_idname, text="Draw Edit Motions")


# Register and add to the "view" menu (required to also use F3 search "Modal Draw Operator" for quick access).
def register():
    bpy.utils.register_class(DrawEditMotionsOperator)
    bpy.types.VIEW3D_MT_view.append(menu_func)


def unregister():
    bpy.utils.unregister_class(DrawEditMotionsOperator)
    bpy.types.VIEW3D_MT_view.remove(menu_func)


if __name__ == "__main__":
    register()