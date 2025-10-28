# Background Image Setup Guide

## Image Directory
Place all background images in: `static/images/`

## Supported Formats
- `.jpg` / `.jpeg`
- `.png` 
- `.webp`

## Recommended Image Specifications
- **Resolution**: 1920x1080 or higher (16:9 aspect ratio)
- **File Size**: Under 2MB for fast loading
- **Quality**: High quality but web-optimized

## Image Naming Convention
Use descriptive, lowercase names with underscores:
- `dungeon_entrance.jpg`
- `forest_clearing.jpg`
- `tavern_interior.jpg`
- `battle_arena.jpg`
- `treasure_room.jpg`
- `dark_cave.jpg`
- `castle_courtyard.jpg`

## How to Use Background Images

### In Your Game Code:
```python
from game.scene_manager import create_scene_event, dungeon_entrance_scene

# Method 1: Use helper functions
events.append(dungeon_entrance_scene())

# Method 2: Create custom scenes
events.append(create_scene_event("forest_clearing.jpg", "You emerge into a peaceful clearing..."))

# Method 3: Just change background without text
events.append(create_scene_event("castle_courtyard.jpg"))

# Method 4: Clear background
events.append(create_scene_event(None, "You enter a dark void..."))
```

### Example Event Structure:
```python
scene_event = {
    "type": "scene",
    "data": {
        "background": "dungeon_entrance.jpg",  # Image filename
        "text": "You stand before the ancient dungeon..."  # Optional overlay text
    }
}
```

## Image Sources (Free/Legal)
Recommended sources for fantasy/DnD images:
- **Unsplash**: unsplash.com (search: fantasy, medieval, castle, forest)
- **Pixabay**: pixabay.com (fantasy category)
- **Pexels**: pexels.com (medieval, nature themes)
- **Artstation**: artstation.com (concept art, with permission)

## Testing Your Images
1. Place image in `static/images/`
2. Test with: `create_scene_event("your_image.jpg", "Test text")`
3. Check browser developer tools for any loading errors
4. Verify image displays correctly at different screen sizes

## Current Image Slots Ready to Use:
- `dungeon_entrance.jpg` - Main dungeon entrance
- `forest.jpg` - Forest/outdoor scenes  
- `tavern.jpg` - Inn/tavern interiors
- `battle.jpg` - Combat encounters
- `treasure_room.jpg` - Loot/treasure discoveries
- `dark_cave.jpg` - Underground/cave scenes
- `castle_courtyard.jpg` - Castle/fortress areas

## Visual Effect Tips:
- Dark/atmospheric images work best for text readability
- Images with empty space in bottom half are ideal for text overlay
- High contrast images provide better text visibility
- Consider the mood: bright for safe areas, dark for dangerous ones