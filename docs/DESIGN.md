# Visual identity

Maxkompilator uses a vivid, dimensional science-fiction style: a colorful 3D
identity, dark working surfaces and clear controls. This is the visual direction
for the project and a reference for future Swir applications.

## App icon

The primary mark is a sculpted **M**, with cyan glass, magenta and violet depth,
orange highlights, brushed metal and a small lime energy core. Its broad shape
keeps the application recognizable when the icon is reduced for a taskbar.

- Application asset: [`assets/maxkompilator.png`](../assets/maxkompilator.png), a
  **512 × 512** PNG with a transparent background, exported from the original
  3D artwork for desktop and documentation use.
- Runtime copy: `maxkompilator/assets/maxkompilator.png`. It must match the source
  byte for byte and be included in the Python wheel.
- Windows: `scripts/build_windows.py` exports an ICO containing **16, 24, 32, 48,
  64, 128 and 256 pixel** images. Both the desktop EXE and its console worker use
  this icon; the GUI loads the packaged PNG.

Preserve the transparent margin and the complete silhouette. Do not place a
square background behind the mark or flatten its material highlights. Future
application icons can use their own recognizable symbol while keeping this
family of vivid colors, thick bevels, translucent surfaces and polished metal.

## Interface palette

| Role | Color | Use |
|---|---|---|
| Window | `#090D19` | Main background |
| Panel | `#11182A` | Project, result and log panels |
| Primary text | `#EDF0FC` | Labels and working content |
| Secondary text | `#A3AFC8` | Hints and descriptions |
| Cyan | `#52DED9` | Result panel, focus and links |
| Violet | `#B779FF` | Configuration panel |
| Magenta | `#EB53D3` | Identity accents |
| Orange | `#FF9873` | Log panel accent |
| Lime | `#DCF586` | Small identity highlights |

The main build action uses a violet-to-magenta gradient. A thin spectrum line
connects the header to the workspace. Most of the window stays dark so paths,
logs and error messages remain easy to read during long builds.

## Interaction rules

- Give every action a clear text label. Color supplements the label.
- Keep output, validation and runtime-test results distinguishable in the text.
- Show live logs and a busy indicator during work; keep cancellation available.
- Preserve visible keyboard focus, readable disabled states and useful tooltips.
- Keep the **by Swir** link in the header: <https://github.com/Swir>.
- Product documentation is in English. The current desktop interface is in
  Polish; changing the visual identity does not change its language.

## Checking a visual change

Run `python scripts/gui_smoke.py --screenshot build/gui-smoke.png` with the GUI
dependencies installed. Inspect the screenshot for clipped labels, contrast,
icon transparency and layout at the supported window size. The Windows CI gate
also opens the actual packaged application twice and records separate reports
and screenshots. Its automated offscreen checks do not replace an interactive
desktop review.
