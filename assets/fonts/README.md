# Fonts

The level-up card (`/card` slash command) is rendered with Pillow.

If you drop `Inter-Regular.ttf` and `Inter-Bold.ttf` into this folder, the card generator picks them up automatically. Inter is the design we tuned for.

If those files don't exist, the generator falls back to (in order):
  1. macOS system fonts (Helvetica, Arial)
  2. Linux DejaVu Sans (bundled with Pillow)
  3. PIL's default bitmap font

The card will still render — it just looks slightly different with the fallback fonts.

## Adding Inter

Inter is free and open-source under the SIL Open Font License. Download from:

  https://rsms.me/inter/  (download the .zip, extract `Inter-Regular.ttf` and `Inter-Bold.ttf`)

Place the two `.ttf` files directly in this directory.
