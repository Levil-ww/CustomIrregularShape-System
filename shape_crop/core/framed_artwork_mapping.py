"""Sample a complete independent picture over its original repeating background."""
import numpy as np
from shape_crop.core.sampling import sample, sample_curved_inset, sample_perimeter_strip
from shape_crop.core.renderer import blend
from shape_crop.core.geometry import ArcBand


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
    if (frame.uniform_texture and isinstance(shape, ArcBand) and
            shape.half_height-inner.half_height < inset-1e-8):
        # The generic inset cap reaches zero at semicircular ends. These two
        # texture panels still have a valid parallel arc with the same centre.
        radius, half_height = shape.radius-inset, shape.half_height-inset
        width = shape.diameter-2*inset
        chord = 2*(shape.center+np.sqrt(max(0.,radius**2-half_height**2)))
        if 0 < chord < width:
            minimum_chord = width-2*half_height
            if frame.stroke.size:
                minimum_chord = np.nextafter(minimum_chord,np.inf)
            inner = ArcBand(width, 2*half_height, max(chord,minimum_chord))
    depth=inner.depth(x,y)
    if frame.native_margins:
        result = _sample_source_margins(layout,shape.inset(border_cm),inner,artwork.box,x,y)
    thickness=frame.stroke.shape[0]*native_scale
    a,b,c,d=frame.box
    scale=max((inner.diameter-2*thickness)/(c-a),(inner.height-2*thickness)/(d-b))
    picture=layout.image[b:d,a:c]
    flowers=(sample(picture,x/scale+(c-a-1)/2,y/scale+(d-b-1)/2)
             if thickness or frame.uniform_texture else
             sample_curved_inset(picture,inner,x,y))
    blend(result,flowers,np.clip((depth-thickness)/pixel_cm+.5,0,1))
    if thickness:
        stroke=(sample_perimeter_strip(frame.stroke,inner.boundary_coordinate(x,y),
                depth/native_scale-.5,inner.perimeter,native_scale,0.) if frame.repeat_stroke else
                sample(frame.stroke,np.zeros_like(depth),depth/native_scale-.5))
        coverage=np.clip(depth/pixel_cm+.5,0,1)*np.clip((thickness-depth)/pixel_cm+.5,0,1)
        blend(result,stroke,coverage)
    return result


def _sample_source_margins(layout, outer, inner, box, x, y):
    """Continuously map the original four margins around an outlined panel."""
    a,b,c,d = box
    left,top,right,bottom = layout.content_box_px
    ay = np.abs(y)
    cy = (b+d-1)/2
    half_y = (d-b)/2
    gap_y = np.where(y>=0,bottom-d,b-top)
    fraction_y = np.clip((ay-inner.half_height)/max(outer.half_height-inner.half_height,1e-6),0,1)
    offset_y = np.where(ay<=inner.half_height,ay/inner.half_height*half_y,
                        half_y+fraction_y*gap_y)
    v = cy+np.where(y>=0,offset_y,-offset_y)
    def extent(contour):
        return getattr(contour,'center',0.)+np.sqrt(np.maximum(0.,contour.radius**2-
            np.minimum(ay,contour.half_height)**2))
    inside,outside = extent(inner),extent(outer)
    fraction_x = np.clip((np.abs(x)-inside)/np.maximum(outside-inside,1e-6),0,1)
    cx = (a+c-1)/2
    gap_x = np.where(x>=0,right-c,a-left)
    u = cx+np.sign(x)*(np.minimum(np.abs(x)/np.maximum(inside,1e-6),1)*(c-a)/2+
                       fraction_x*gap_x)
    full_row = (left+right-1)/2+x/np.maximum(outside,1e-6)*(right-left-1)/2
    u = u*(1-fraction_y)+full_row*fraction_y
    return sample(layout.image,np.clip(u,left,right-1),np.clip(v,top,bottom-1))
