"""Sample a complete independent picture over its original repeating background."""
import numpy as np
from shape_crop.core.sampling import sample
from shape_crop.core.renderer import blend


def sample_framed_artwork(layout, mapping, native_scale, x, y, pixel_cm):
    artwork = layout.framed_artwork
    ox, oy = artwork.origin
    u = x / native_scale + (layout.width_px - 1) / 2 - ox
    v = y / native_scale + (layout.height_px - 1) / 2 - oy
    result = sample(artwork.tile, u, v, wrap_x=True, wrap_y=True)
    left, top, right, bottom = (round(value) for value in artwork.box)
    picture = layout.image[top:bottom, left:right]
    u = x / mapping.scale_cm + mapping.centre_x - left
    v = y / mapping.scale_cm + mapping.centre_y - top
    distance = np.minimum(np.minimum(u + .5, right - left - .5 - u),
                          np.minimum(v + .5, bottom - top - .5 - v)) * mapping.scale_cm
    coverage = np.clip(distance / pixel_cm + .5, 0, 1)
    blend(result, sample(picture, u, v), coverage)
    return result


def sample_contoured_frame(layout, shape, native_scale, border_cm, x, y, pixel_cm):
    """Curve the double outline while sampling the floral fill uniformly."""
    artwork=layout.framed_artwork
    frame=layout.contoured_frame
    ox,oy=artwork.origin
    result=sample(artwork.tile,x/native_scale+(layout.width_px-1)/2-ox,
                  y/native_scale+(layout.height_px-1)/2-oy,wrap_x=True,wrap_y=True)
    extra=max(0,border_cm-layout.border_depth_px*native_scale)
    inset=frame.inset_px*native_scale+extra
    if inset>=shape.half_height:
        raise ValueError('当前尺寸无法保留内侧花纹框，请增大尺寸')
    inner=shape.inset(inset)
    depth=inner.depth(x,y)
    thickness=frame.stroke.shape[0]*native_scale
    a,b,c,d=frame.box
    scale=max((inner.diameter-2*thickness)/(c-a),(inner.height-2*thickness)/(d-b))
    picture=layout.image[b:d,a:c]
    flowers=sample(picture,x/scale+(c-a-1)/2,y/scale+(d-b-1)/2)
    blend(result,flowers,np.clip((depth-thickness)/pixel_cm+.5,0,1))
    stroke=sample(frame.stroke,np.zeros_like(depth),depth/native_scale-.5)
    coverage=np.clip(depth/pixel_cm+.5,0,1)*np.clip((thickness-depth)/pixel_cm+.5,0,1)
    blend(result,stroke,coverage)
    return result
