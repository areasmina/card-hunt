# Card Hunt brand assets

Vintage 1993-95 card look. The frame textures are stitched from scans of real cards
(personal, non-profit fan app; suggested footer: "Unofficial fan project, not affiliated with
Wizards of the Coast"). The mascot is an original pixel-art monkey card hunter.

| File | Size | Use |
| --- | --- | --- |
| `logo-card-dark.png`, `logo-card-light.png` | 1000×1400, transparent corners | Logo card (black frame for the dark theme, white frame for the light one) |
| `logo-card-dark-400.png` | 400 wide | Small copy |
| `logo-card-back.png` | 1000×1400 | Our own card back (monkey + name) |
| `logo-wordmark-dark.png`, `logo-wordmark-light.png` | 2400×900, transparent corners | Header wordmark |
| `logo-wordmark-*-720.png` | 720 wide | Header-sized copies |
| `icon-1024.png` | 1024×1024 | Master app icon (PWA icons in `../icons/`) |
| `card-spin.webm` | 800×800, 3.2 s loop at 15 fps, transparent | Pixel card spin (Chrome, Firefox, Edge) |
| `card-spin-dark.mp4`, `card-spin-light.mp4` | 800×800 on #121412 / #f1ebdf | Safari fallback per theme |
| `textures/*.jpg` | 1024, seamless | Frame and text-box tiles for the UI (`hires/` = 2048) |
| `vintage/monkey-*.png` | 64 px pixel art | The mascot: sprite, art scene, head, icon crop |

How it's made:
- `quilt.py` stitches seamless tiles from the scans, `upres.py` lifts them to 2048 in Blender.
- `monkey.py` draws the monkey (Python + Pillow).
- `vintage.py` (Blender 5.2) renders the cards, wordmarks, icons and the spin:
  `blender -b -P vintage.py -- cards,wordmark,icon,anim,encode` → `out/vintage/`.
- `textures.py` / `build.py` are the earlier procedural and retro experiments.
