# Card Hunt brand assets

Retro look: worn ink stamp on cream paper (ink #1b1a17, red #c8402a, paper #efe6d2), plus a Game Boy style pixel animation. Rendered in Blender 5.2 from `build.py`. All artwork is original.

| File | Size | Use |
| --- | --- | --- |
| `logo-badge.png` | 1600×1600 on paper | Round stamp badge |
| `logo-badge-transparent.png` | 1600×1600, transparent | Badge to place on any light background |
| `logo-badge-inverse.png` | 1600×1600 | Cream on red |
| `logo-wordmark.png` | 2400×900, transparent | Badge + boxed "CARD HUNT" wordmark |
| `logo-wordmark-paper.png` | 2400×900 on paper | Same on paper |
| `logo-wordmark-inverse.png` | 2400×900 | Cream on red |
| `logo-wordmark-720.png`, `logo-badge-256.png` | small | Header-sized copies |
| `icon-1024.png` | 1024×1024 | Master app icon |
| `card-spin.webm` | 800×800, 3.2 s loop at 15 fps, transparent | Pixel card spin (Chrome, Firefox, Edge) |
| `card-spin.mp4` | 800×800 on #f2eee4 | Safari fallback |
| `*.blend` | | Open in Blender to tweak |

PWA icons in `../icons/` come from the same scene. Rebuild on Windows with
`blender -b -P build.py -- logo|icon|anim|encode`; output goes to `out/`.
