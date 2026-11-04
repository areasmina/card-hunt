import sys, os, glob
import numpy as np
from PIL import Image
src, NAT = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 96
fs = sorted(glob.glob(os.path.join(src, 'f*.png')))
sm = [Image.open(f).convert('RGBA').resize((NAT, NAT), Image.BOX) for f in fs]
# one shared palette for every frame (no flicker): k-means over all opaque pixels
px = np.concatenate([np.asarray(s)[..., :3][np.asarray(s)[..., 3] > 128] for s in sm]).astype(np.float32)
rng = np.random.default_rng(0); P = px[rng.choice(len(px), 24, replace=False)]
for _ in range(25):
    sub = px[rng.choice(len(px), min(len(px), 60000), replace=False)]
    lab = ((sub[:, None] - P[None]) ** 2).sum(-1).argmin(1)
    for k in range(len(P)):
        if (lab == k).any(): P[k] = sub[lab == k].mean(0)
BAYER = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) + .5) / 16
yy, xx = np.mgrid[0:NAT, 0:NAT]
out = []
for s in sm:
    a = np.asarray(s).astype(np.float32)
    rgb = a[..., :3] + ((BAYER[yy % 4, xx % 4] - .5) * 14)[..., None]
    q = P[((rgb[..., None, :] - P) ** 2).sum(-1).argmin(-1)]
    al = (a[..., 3] > 110) * 255
    out.append(Image.fromarray(np.dstack([q, al]).astype(np.uint8), 'RGBA'))
UP = 2
big = [o.resize((NAT * UP, NAT * UP), Image.NEAREST) for o in out]
big[0].save('badge-hand.webp', save_all=True, append_images=big[1:], duration=100, loop=0, lossless=True)
big[len(big) * 52 // 100].save('badge-hand.png')
# preview sheet on the app's dark bg + smooth version
sheet = Image.new('RGBA', (8 * 200, 200), (38, 42, 43, 255))
for k in range(8): sheet.alpha_composite(big[int(len(big) * k / 8)], (k * 200 + 4, 4))
sheet.save('badge-hand-sheet.png'); print('ok', len(out))
