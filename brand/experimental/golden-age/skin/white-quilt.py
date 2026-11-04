import sys, os, importlib.util
sys.argv=[sys.argv[0]]
spec=importlib.util.spec_from_file_location('q','/home/claude/card-hunt/brand/quilt.py'); q=importlib.util.module_from_spec(spec); spec.loader.exec_module(q)
import numpy as np
from PIL import Image
q.SCALE={'rector':0.9}
src=[('rector',(48,115,72,560)),('rector',(48,635,72,905)),('swords',(40,95,66,500)),('swords',(606,95,630,500)),('divine',(42,95,68,500)),('divine',(608,95,632,500)),('divine',(42,565,64,825))]
srcs=[]
for f,b in src:
    a=q.load('wscan',f,b); L=a.mean(2,keepdims=True); a=(L-L.mean())/L.std()  # luminance, normalised per source so the three cards blend
    srcs.append(np.repeat(a*16+190,3,2))
t=q.quilt(srcs,seed=11)
L=t[...,0]
# rank-match to a mild cream-grey: mean 196, std 14
z=(L-L.mean())/L.std(); out=np.clip(196+z*14,0,255)
rgb=np.dstack([out+2,out,out-6]).clip(0,255).astype(np.uint8)
im=Image.fromarray(rgb).resize((q.N*3,q.N*3),Image.LANCZOS)
im.save('frame-white-new.jpg',quality=90); print(im.size)
