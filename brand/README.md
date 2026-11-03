# Card Hunt brand assets

Rendered in Blender 5.2 from `build.py`. All artwork is original (no MTG card art).

| File | Size | Use |
| --- | --- | --- |
| `logo-light.png` | 2400×900, transparent | Logo for light backgrounds (purple wordmark) |
| `logo-dark.png` | 2400×900, transparent | Logo for dark backgrounds (white wordmark) |
| `icon-1024.png` | 1024×1024, transparent | Master app icon |
| `card-spin.webm` | 800×800, 4 s loop, transparent (VP9 alpha) | Spinning card, Chrome/Firefox/Edge |
| `card-spin.mp4` | 800×800, 4 s loop, on #f6f6f8 | Spinning card fallback for Safari |
| `card-front.png`, `card-back.png` | 1000×1400 | Flat card face textures |
| `*.blend` | | Open in Blender to tweak |

The PWA icons in `../icons/` (192, 512, maskable 512, apple-touch 180) come from the same scene.

Rebuild (Windows):

```
blender -b -P build.py -- logo
blender -b -P build.py -- icon
blender -b -P build.py -- anim
blender -b -P build.py -- encode
```

Output goes to `out/`.
