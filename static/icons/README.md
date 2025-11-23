# PWA Icons

This directory contains app icons for the Progressive Web App (PWA).

## Required Icon Sizes

The following icon sizes are needed for full PWA support:

- `icon-72x72.png` - Small icon
- `icon-96x96.png` - Small icon
- `icon-128x128.png` - Medium icon
- `icon-144x144.png` - Medium icon
- `icon-152x152.png` - iOS icon
- `icon-192x192.png` - **Required** - Android standard icon (maskable)
- `icon-384x384.png` - Large icon
- `icon-512x512.png` - **Required** - Android large icon (maskable)

## Creating Icons

### Quick Method (Using Existing Logo)
If you have a logo image, use an online tool like:
- https://realfavicongenerator.net/
- https://www.pwabuilder.com/imageGenerator

### Design Guidelines

1. **Simple & Recognizable**: Use a simple design that's recognizable at small sizes
2. **Safe Zone**: For maskable icons, keep important content within the center 80%
3. **Background**: Use a solid color background (theme color: `#8b5cf6`)
4. **Format**: PNG with transparency
5. **Content**:
   - Consider using the palm tree emoji (🌴) as the main element
   - Add "LA" text or "Events" text if space permits
   - Use white or light colors on the purple background

### Temporary Placeholder

Until proper icons are created, you can use a simple colored square:
```bash
# Generate simple placeholder (requires ImageMagick)
for size in 72 96 128 144 152 192 384 512; do
  convert -size ${size}x${size} xc:'#8b5cf6' \
    -gravity center \
    -pointsize $(($size / 3)) \
    -fill white \
    -font Arial-Bold \
    -annotate +0+0 '🌴' \
    icon-${size}x${size}.png
done
```

### Maskable Icons

Android adaptive icons require a "maskable" version with safe zones:
- Keep logo/text in center 80% of the image
- Fill entire background with theme color
- Test at https://maskable.app/

## Current Status

⚠️ **Action Required**: PWA icons need to be created and placed in this directory.

The manifest.json references these icons, but they don't exist yet. The PWA will work but won't show proper icons until these are created.

## Testing

After adding icons, test your PWA:
1. Open the site in Chrome/Edge on Android or Safari on iOS
2. Check the install prompt appears
3. Install the app
4. Verify icons appear correctly on the home screen
5. Test maskable icons at: https://maskable.app/
