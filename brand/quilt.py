"""Seamless tiles stitched from real card-frame pixels (image quilting, Efros & Freeman 2001).
python3 quilt.py <scan dir> <out dir>   - patches are copied from the scans, never generated."""
import sys, os
import numpy as np
from PIL import Image

B, O = 16, 5        # block and overlap, in scan pixels
N = 32 * (B - O)    # tile size in scan pixels (352), seamless
UP = int(os.environ.get('UP', 3))  # 1 = native scan resolution (for the upscaler)

SRC = {
    'frame-black':    [('4c6801b6', (18, 62, 44, 555)), ('4c6801b6', (424, 112, 448, 555))],
    'frame-blue':     [('d9b58f69', (17, 60, 34, 290)), ('d9b58f69', (344, 60, 362, 285))],
    'frame-artifact': [('cdd8ede2', (21, 75, 42, 355)), ('cdd8ede2', (428, 75, 449, 355)), ('cdd8ede2', (21, 400, 42, 580))],
    'frame-white':    [('c2da39b0', (4, 40, 15, 300)), ('c2da39b0', (221, 40, 233, 300)), ('c2da39b0', (140, 318, 232, 336))],
    'box-black':      [('4c6801b6', (296, 530, 408, 568)), ('4c6801b6', (282, 402, 406, 424))],
    'box-white':      [('c2da39b0', (24, 210, 210, 231)), ('c2da39b0', (24, 280, 212, 298))],
    'box-blue':       [('d9b58f69', (232, 428, 334, 466))],
    'box-artifact':   [('cdd8ede2', (250, 486, 410, 504))],
}


SCALE = {'c2da39b0': 2, 'db9f516e': 0.6}  # bring every scan to about the same print scale


def load(scan_dir, f, box):
    im = Image.open(os.path.join(scan_dir, f + '-image.jpg')).convert('RGB').crop(box)
    k = SCALE.get(f, 1)
    if k != 1:
        im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    return np.asarray(im).astype(np.float32)


def candidates(srcs, b, stride):
    out = []
    for s in srcs:
        h, w = s.shape[:2]
        if h < b or w < b:
            continue
        for y in range(0, h - b + 1, stride):
            for x in range(0, w - b + 1, stride):
                out.append(s[y:y + b, x:x + b])
    return np.stack(out)


def min_cut(err):
    """err: (rows, cols) cost; returns mask (rows, cols) True = keep new block, cutting top-to-bottom."""
    r, c = err.shape
    E = err.copy()
    for i in range(1, r):
        prev = np.pad(E[i - 1], 1, constant_values=np.inf)
        E[i] += np.minimum(np.minimum(prev[:-2], prev[1:-1]), prev[2:])
    path = np.zeros(r, int)
    path[-1] = int(np.argmin(E[-1]))
    for i in range(r - 2, -1, -1):
        j = path[i + 1]
        lo, hi = max(0, j - 1), min(c, j + 2)
        path[i] = lo + int(np.argmin(E[i, lo:hi]))
    mask = np.zeros((r, c), bool)
    for i in range(r):
        mask[i, path[i]:] = True
    return mask


def quilt(srcs, seed=1):
    rng = np.random.default_rng(seed)
    S = B - O
    k = N // S
    out = np.zeros((N, N, 3), np.float32)
    filled = np.zeros((N, N), bool)
    cands = candidates(srcs, B, 1)
    for bi in range(k):
        for bj in range(k):
            ys = (np.arange(B) + bi * S) % N
            xs = (np.arange(B) + bj * S) % N
            cur = out[np.ix_(ys, xs)]
            fm = filled[np.ix_(ys, xs)]
            if fm.any():
                diff = ((cands - cur[None]) ** 2).sum(-1) * fm[None]
                cost = diff.reshape(len(cands), -1).sum(1)
                best = cost.min()
                pick = rng.choice(np.flatnonzero(cost <= best * 1.12 + 1e-6))
            else:
                pick = rng.integers(len(cands))
            blk = cands[pick]
            keep = np.ones((B, B), bool)
            e = ((blk - cur) ** 2).sum(-1)
            if fm[:, :O].all():                  # left overlap
                keep[:, :O] &= min_cut(e[:, :O])
            if fm[:O, :].all():                  # top overlap
                keep[:O, :] &= min_cut(e[:O, :].T).T
            if fm[:, -O:].all():                 # wrap: right overlap (last column)
                keep[:, -O:] &= ~min_cut(e[:, -O:])
            if fm[-O:, :].all():                 # wrap: bottom overlap (last row)
                keep[-O:, :] &= ~min_cut(e[-O:, :].T).T
            keep |= ~fm
            # soften the cut by 1px
            new = np.where(keep[..., None], blk, cur)
            out[np.ix_(ys, xs)] = new
            filled[np.ix_(ys, xs)] = True
    return out


if __name__ == '__main__':
    scan_dir, out_dir = sys.argv[1], sys.argv[2]
    only = sys.argv[3:] or list(SRC)
    os.makedirs(out_dir, exist_ok=True)
    for name in only:
        srcs = [load(scan_dir, f, b) for f, b in SRC[name]]
        t = Image.fromarray(quilt(srcs).clip(0, 255).astype(np.uint8))
        t = t.resize((N * UP, N * UP), Image.LANCZOS)
        t.save(os.path.join(out_dir, name + ('.png' if UP == 1 else '.jpg')), quality=92)
        print('wrote', name)
