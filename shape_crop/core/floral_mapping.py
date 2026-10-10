"""Map inset textures and whole corner artwork as independent source layers."""
import numpy as np
from shape_crop.core.sampling import sample
from shape_crop.core.renderer import blend


def sample_patterned_inset(layout,mapping,shape,border_cm,x,y,pixel_cm):
    panel=layout.patterned_inset
    a,b,c,d=panel.box
    _,top,_,bottom=layout.content_box_px
    gap=((b-top)+(bottom-d))/2/(bottom-top)
    inner=shape.inset(border_cm+gap*(shape.height-2*border_cm))
    scale=max(inner.diameter/(c-a),inner.height/(d-b))
    u=x/scale+(c-a-1)/2; v=y/scale+(d-b-1)/2
    result=np.empty(np.broadcast_shapes(x.shape,y.shape)+(3,),dtype=np.uint8)
    result[:]=panel.background
    picture=sample(layout.image[b:d,a:c],u,v)
    blend(result,picture,np.clip(inner.depth(x,y)/pixel_cm+.5,0,1))
    return result


def corner_transforms(layout,shape,scale):
    transforms=[]
    for group in layout.corner_composition.groups:
        a,b,c,d=group.box; width,height=c-a,d-b
        fit=min(scale*.8,shape.height*.46/height,shape.diameter*.30/width)
        cy=(-shape.half_height+.25+height*fit/2) if group.anchor=='top_right' else (shape.half_height-.25-height*fit/2)
        rows=np.linspace(0,height-1,min(height,256)).astype(int)
        offsets=[]
        for row in rows:
            columns=np.flatnonzero(group.alpha[row]>32)
            if not columns.size: continue
            yy=cy+(row-(height-1)/2)*fit
            extent=getattr(shape,'center',0.)+np.sqrt(max(0.,shape.radius**2-yy**2))
            reach=(columns[-1]-(width-1)/2)*fit if group.anchor=='top_right' else ((width-1)/2-columns[0])*fit
            offsets.append(extent-reach)
        cx=max(0.,min(offsets)-.25)
        if group.anchor=='bottom_left': cx=-cx
        transforms.append((group,fit,cx,cy))
    return tuple(transforms)


def sample_corner_composition(layout,transforms,scale,x,y,rgb):
    for group,fit,cx,cy in transforms:
        a,b,c,d=group.box
        u=(x-cx)/fit+(c-a-1)/2; v=(y-cy)/fit+(d-b-1)/2
        inside=(u>=0)&(u<=c-a-1)&(v>=0)&(v<=d-b-1)
        alpha=sample(group.alpha[...,None],u,v)[...,0]/255.*inside
        blend(rgb,sample(layout.image[b:d,a:c],u,v),alpha)
    a,b,c,d=layout.corner_composition.text_box
    u=x/scale+(c-a-1)/2; v=y/scale+(d-b-1)/2
    inside=(u>=0)&(u<=c-a-1)&(v>=0)&(v<=d-b-1)
    blend(rgb,sample(layout.image[b:d,a:c],u,v),inside.astype(float))
    return rgb
