# ALttPRainbowSprite
Randomize mail colors for sprites from The Legend of Zelda: A Link to the Past (SNES)

DEFUALT USAGE: Drag and drop!  Place this script in a directory with a .sfc
ALttP JP 1.0 ROM (currently only tested with roms generated with
Archipelago) and a ./sprites/ subdirectory with at least one .zspr file,
like so:

```
./ALttPRainbowSprite.py
./P8_player_aaML8QIXQRWp9DY4PTLq8g.sfc
./sprites/dragonite.2.zspr
```

Drag the ROM onto the python script, which should generate a patched ROM (with
the "patched_" prefix) if the script ran successfully.  The patched ROM has
random sprite on event enabled with 32 palette-shuffled variants of the
sprites in the ./sprites/ folder.

ALTERNATE USAGE: To create rainbow .zspr files for use in other patchers,
rather than patching a ROM file with random sprite on event, run this script
on the command line like so:

```
python .\ALttPRainbowSprite.py --zspr_out
or: python .\ALttPRainbowSprite.py --zspr_out --zspr_out_count 100
```

This takes a sprite from the ./sprites/ folder and creates 200
(or `--zspr_out_count`) palette-shuffled variants of that sprite in the
./output/ directory.

THIS DOES NOT WORK WITH ALL SPRITES!  The process for adding a sprite to
this script is as follows:

1) Obtain the .zspr and .png versions of the sprite (SpriteSomething is
   useful here)

2) Load the sprite in SpriteSomething and the .png in GIMP or your photo
   editor of choice.

3) Find which palette entries need to remain unaffected by this script, which
   entries correspond to unique mail hues, and which entries correspond to
   lighter shades of those hues.  For example, the default link sprite has
   three mail hues: Jerkin (green/blue/red), hat (green/yellow/purple), and
   sleeves (brown/orange/green), and the jerkin and hat hues have light/dark
   shades, with indices B1 B2 (jerkin), B3 B4 (hat), and B6 (sleeves).

4) Add the sprite name and indices to `shuffle_mail_palette()` to extend this
   script to work with the new sprite.
