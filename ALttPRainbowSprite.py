# Copyright 2023, krelbel
# SPDX-License-Identifier: MIT

import logging
import argparse
import os
import random
from pathlib import Path
from urllib.request import urlopen
import json
from glob import glob
from urllib.parse import urlparse
import shutil
import struct
import math
import colorsys

__version__ = '0.1'

# Patches a random sprite on event rom to include all the sprites in ./sprites/
# 
# DEFUALT USAGE: Drag and drop!  Place this script in a directory with a .sfc
# ALttP JP 1.0 ROM (currently only tested with roms generated with
# Archipelago) and a ./sprites/ subdirectory with at least one .zspr file,
# like so:
#
# ./ALttPRainbowSprite.py
# ./P8_player_aaML8QIXQRWp9DY4PTLq8g.sfc
# ./sprites/dragonite.2.zspr
#
# Drag the ROM onto the python script, which should generate a patched ROM (with
# the "patched_" prefix) if the script ran successfully.  The patched ROM has
# random sprite on event enabled with 32 palette-shuffled variants of the
# sprites in the ./sprites/ folder.
#
# ALTERNATE USAGE: To create rainbow .zspr files for use in other patchers,
# rather than patching a ROM file with random sprite on event, run this script
# on the command line like so:
#
# python .\ALttPRainbowSprite.py --zspr_out
# or: python .\ALttPRainbowSprite.py --zspr_out --zspr_out_count 100
#
# This takes a sprite from the ./sprites/ folder and creates 200
# (or --zspr_out_count) palette-shuffled variants of that sprite in the
# ./output/ directory.
#
# THIS DOES NOT WORK WITH ALL SPRITES!  The process for adding a sprite to
# this script is as follows:
#
# 1) Obtain the .zspr and .png versions of the sprite (SpriteSomething is
#    useful here)
#
# 2) Load the sprite in SpriteSomething and the .png in GIMP or your photo
#    editor of choice.
#
# 3) Find which palette entries need to remain unaffected by this script, which
#    entries correspond to unique mail hues, and which entries correspond to
#    lighter shades of those hues.  For example, the default link sprite has
#    three mail hues: Jerkin (green/blue/red), hat (green/yellow/purple), and
#    sleeves (brown/orange/green), and the jerkin and hat hues have light/dark
#    shades, with indices B1 B2 (jerkin), B3 B4 (hat), and B6 (sleeves).
#
# 4) Add the sprite name and indices to shuffle_mail_palette() to extend this
#    script to work with the new sprite.

# General rom patching logic copied from https://github.com/LLCoolDave/ALttPEntranceRandomizer
def write_byte(array, address, value):
    array[address] = value

# .zspr file dumping logic copied with permission from SpriteSomething:
# https://github.com/Artheau/SpriteSomething/blob/master/source/meta/classes/spritelib.py#L443 (thanks miketrethewey!)
def dump_zspr(spritename, authorname, authorshortname, basesprite, basepalette, baseglove, outfilename):
    palettes = basepalette
    # Add glove data
    palettes.extend(baseglove)
    HEADER_STRING = b"ZSPR"
    VERSION = 0x01
    SPRITE_TYPE = 0x01  # this format has "1" for the player sprite
    RESERVED_BYTES = b'\x00\x00\x00\x00\x00\x00'
    QUAD_BYTE_NULL_CHAR = b'\x00\x00\x00\x00'
    DOUBLE_BYTE_NULL_CHAR = b'\x00\x00'
    SINGLE_BYTE_NULL_CHAR = b'\x00'

    write_buffer = bytearray()

    write_buffer.extend(HEADER_STRING)
    write_buffer.extend(struct.pack('B', VERSION)) # as_u8
    checksum_start = len(write_buffer)
    write_buffer.extend(QUAD_BYTE_NULL_CHAR) # checksum
    sprite_sheet_pointer = len(write_buffer)
    write_buffer.extend(QUAD_BYTE_NULL_CHAR)
    write_buffer.extend(struct.pack('<H', len(basesprite))) # as_u16
    palettes_pointer = len(write_buffer)
    write_buffer.extend(QUAD_BYTE_NULL_CHAR)
    write_buffer.extend(struct.pack('<H', len(palettes))) # as_u16
    write_buffer.extend(struct.pack('<H', SPRITE_TYPE)) # as_u16
    write_buffer.extend(RESERVED_BYTES)
    # sprite.name
    #write_buffer.extend(outfilename.encode('utf-16-le'))
    write_buffer.extend(spritename.encode('utf-16-le'))
    write_buffer.extend(DOUBLE_BYTE_NULL_CHAR)
    # author.name
    #write_buffer.extend("ALttPLinkSpriteShuffler".encode('utf-16-le'))
    write_buffer.extend(authorname.encode('utf-16-le'))
    write_buffer.extend(DOUBLE_BYTE_NULL_CHAR)
    # author.name-short
    #write_buffer.extend("SpriteShuffler".encode('ascii'))
    write_buffer.extend(authorshortname.encode('ascii'))
    write_buffer.extend(SINGLE_BYTE_NULL_CHAR)
    write_buffer[sprite_sheet_pointer:sprite_sheet_pointer +
                 4] = struct.pack('<L', len(write_buffer)) # as_u32
    write_buffer.extend(basesprite)
    write_buffer[palettes_pointer:palettes_pointer +
                 4] = struct.pack('<L', len(write_buffer)) # as_u32
    write_buffer.extend(palettes)

    checksum = (sum(write_buffer) + 0xFF + 0xFF) % 0x10000
    checksum_complement = 0xFFFF - checksum

    write_buffer[checksum_start:checksum_start +
                 2] = struct.pack('<H', checksum) # as_u16
    write_buffer[checksum_start + 2:checksum_start +
                 4] = struct.pack('<H', checksum_complement) # as_u16

    with open('%s' % outfilename, "wb") as zspr_file:
        zspr_file.write(write_buffer)

def open_zspr(srcfile):
    data = bytearray(open(srcfile, 'rb').read())

    # .zspr import copied with permission from SpriteSomething
    # https://github.com/Artheau/SpriteSomething/blob/master/source/meta/classes/spritelib.py#L131 (thanks miketrethewey!)
    if data[0:4] != bytes(ord(x) for x in 'ZSPR'):
        print("ERROR, invalid .zspr file specified: " + args.zspr_in)
        return
    if data[4] == 1:
        pixel_data_offset = int.from_bytes(
            data[9:13], byteorder='little', signed=False)
        pixel_data_length = int.from_bytes(
            data[13:15], byteorder='little', signed=False)
        palette_data_offset = int.from_bytes(
            data[15:19], byteorder='little', signed=False)
        palette_data_length = int.from_bytes(
            data[19:21], byteorder='little', signed=False)

        if (pixel_data_offset == 0 or
            palette_data_offset == 0 or
            pixel_data_offset + 0x7000 > palette_data_offset or
            pixel_data_offset + 0x7000 > len(data) or
            palette_data_offset + 124 > len(data)):
            print("ERROR, corrupt .zspr file specified: " + args.zspr_in)
            return

        basesprite = data[pixel_data_offset:pixel_data_offset + pixel_data_length]
        basepalette = data[palette_data_offset:palette_data_offset + palette_data_length - 4]
        baseglove = data[palette_data_offset + palette_data_length - 4:palette_data_offset + palette_data_length]

        offset = 29

        i = 0
        byte_size = 2
        null_terminator = b"\x00" * 2
        while data[offset + i:offset + i + byte_size] != null_terminator:
            i += byte_size
        raw_string_slice = data[offset:offset + i]
        spritename = str(raw_string_slice, encoding="utf-16-le")
        # have to add another byte_size to go over the null terminator
        offset += i + byte_size

        i = 0
        byte_size = 2
        null_terminator = b"\x00" * 2
        while data[offset + i:offset + i + byte_size] != null_terminator:
            i += byte_size
        raw_string_slice = data[offset:offset + i]
        authorname = str(raw_string_slice, encoding="utf-16-le")
        # have to add another byte_size to go over the null terminator
        offset += i + byte_size

        i = 0
        byte_size = 1
        null_terminator = b"\x00"
        while data[offset + i:offset + i + byte_size] != null_terminator:
            i += byte_size
        raw_string_slice = data[offset:offset + i]
        authorshortname = str(raw_string_slice, encoding="ascii")
        # have to add another byte_size to go over the null terminator
        offset += i + byte_size

        return spritename, authorname, authorshortname, basesprite, basepalette, baseglove
    else:
        print("ERROR, no support for ZSPR version" + str(int(data[4])))

def write_sprite(rom, sprite, palette, glove, spriteindex, paletteindex, gloveindex):
    for i in range(0x7000):
        write_byte(rom, spriteindex + i, sprite[i])
    for i in range(120):
        write_byte(rom, paletteindex + i, palette[i])
    for i in range(4):
        write_byte(rom, gloveindex + i, glove[i])

def rgb_from_bytes(high, low):
    r = low & 0b11111;
    g = ((high & 0b11) << 3) | (low >> 5);
    b = (high >> 2) & 0b11111;
    return r,g,b

def bytes_from_rgb(r,g,b):
    low = (r & 0b11111) | ((g & 0b111) << 5)
    high = ((g >> 3) & 0b11) | ((b & 0b11111) << 2)
    return high, low

def get_different_color(r,g,b,color_difference_angle):
    h,s,v = colorsys.rgb_to_hsv((r / 31.0), (g / 31.0), (b / 31.0))
    opposite_h = h + color_difference_angle/360.0
    if (opposite_h > 1.0):
        opposite_h = opposite_h - 1.0

    opposite_r, opposite_g, opposite_b = colorsys.hsv_to_rgb(opposite_h, s, v)

    return int(opposite_r * 31.0), int(opposite_g * 31.0), int(opposite_b * 31.0)

def get_random_color(min_s, min_v, max_s, max_v):
    h = random.uniform(0,1.0)
    s = random.uniform(min_s, max_s)
    v = random.uniform(min_v, max_v)

    r,g,b = colorsys.hsv_to_rgb(h,s,v)
    return int(r*31.0), int(g*31.0), int(b*31.0)

# Mail entries are 0BBBBBGG GGGRRRRR 16-bit (endian?).  5 BPC
# Palette block format:
# First valid pixel (A1) is index 0, first entry in second row (B0) is index 7
def shuffle_mail_palette(palette, spritename):
    # Minimum distance between different color sets (i.e. hat/mail/sleeves)
    # on the hue color wheel (in degrees).  Doubled for only two colorsets.
    # Raise minimum to guarantee more variance.  Lower variance to guarantee
    # more similarity.
    min_hue_angle = 30
    max_hue_variance = 360
    indices = list()

    # Indices for each color set need to be in order from darkest to lightest.
    # Maximum of 3 indices
    if (spritename == 'Renoko'):
        indices.append([1]) # Belly/stripes
        indices.append([8,9]) # Body
        indices.append([2,10]) # Hair
    elif (spritename == 'Bel'):
        indices.append([8,9]) # Mail (like Link)
        indices.append([11]) # Sleeves
    elif (spritename == 'Fox Link'):
        indices.append([8,9]) # Mail (like Link)
    elif (spritename == 'Sobble'):
        indices.append([6,14,7,13]) # Body
        indices.append([9,1]) # Horn
    elif (spritename == 'Vaporeon'):
        min_hue_angle = 10
        max_hue_variance = 120
        indices.append([1,2,3,5]) # Body
        indices.append([7,6]) # Frill
    elif (spritename == 'Yoshi'):
        indices.append([8,9,11]) # Body
        indices.append([13,10]) # Shoes
    elif (spritename == 'Khloe'):
        indices.append([8,9]) # Eyes
    elif (spritename == 'Zaruvyen'):
        indices.append([14,6,13]) # Wings
    elif (spritename == 'Dragonite'):
        indices.append([10,7,5]) # Body
        indices.append([9,8]) # Belly
        indices.append([11]) # Eye/wing
    elif (spritename == 'Lapras'):
        indices.append([7,6,5]) # Body
        indices.append([3,2]) # Chest
    elif (spritename == 'Drake The Dragon'):
        indices.append([10,11,12]) # Body/hands
        indices.append([8,9]) # Belly
    elif (spritename == 'Dragonair'):
        indices.append([9,10,8,7]) # Body
        indices.append([5,13]) # Balls?
    elif (spritename == 'Leafeon'):
        indices.append([6,5,14,3]) # Leaf
    elif (spritename == 'Charizard'):
        indices.append([9,10,11]) # Body
        indices.append([7,13]) # Belly
        indices.append([8]) # Wings
    elif (spritename == 'Spyro the Dragon'):
        indices.append([5,13]) # Wings
        indices.append([3,6,11,1,14]) # Horns/tail/body
    elif (spritename == 'Archen'):
        indices.append([1,2,3]) # Belly
        indices.append([5,4]) # Beak?
        indices.append([9,10]) # Back?
    elif (spritename == 'Garnet'):
        min_hue_angle = 10
        max_hue_variance = 120
        indices.append([8,9]) # Chest?
        indices.append([11,10]) # ?
        indices.append([6,5])
    elif (spritename == 'Mog'):
        indices.append([7]) # Nose/pom
        indices.append([9,8]) # Wings!
    elif (spritename == 'Baba'):
        indices.append([0]) # Baba main sprite
        indices.append([1]) # Word background
        indices.append([5,11]) # Keke bunny and flag
    elif (spritename == 'Tunic'):
        indices.append([10,8,9]) # Tunic's tunic
        indices.append([7]) # Scarf
    elif (spritename == 'The Robot'):
        indices.append([8,9]) # Case
    else:
        logger.info("ERROR: unknown sprite %s" % spritename)
        return

    for mail in range(3):
        # Each mail set has len(indices) color sets, and each color set has
        # len(indices[colorset]) shades.

        # For each color set in len(indices), pick a hue a certain angle away
        # from the previous color.
        colorangles = [None] * len(indices)
        colorangles[0] = 0
        if len(indices) == 2:
            colorangles[1] = random.randint(min_hue_angle * 2, max_hue_variance - (min_hue_angle * 2))
        elif len(indices) == 3:
            colorangles[1] = random.randint(min_hue_angle, max_hue_variance - min_hue_angle)

            # Pick another hue some distance from the second. 
            # Try going down
            cointoss = random.randint(0,1)
            if (cointoss == 0):
                # Down too low
                if (colorangles[1] < 2 * min_hue_angle):
                    colorangles[2] = random.randint(colorangles[1] + min_hue_angle, max_hue_variance - min_hue_angle)
                else:
                    colorangles[2] = random.randint(min_hue_angle, colorangles[1] - min_hue_angle)
            else:
                if (colorangles[1] > max_hue_variance - (2 * min_hue_angle)):
                    colorangles[2] = random.randint(min_hue_angle, colorangles[1] - min_hue_angle)
                else:
                    colorangles[2] = random.randint(colorangles[1] + min_hue_angle, max_hue_variance - min_hue_angle)

        for colorset in range(len(indices)):
            if colorset == 0:
                # Define the ranges for saturation/value.  Lowering the max
                # here leaves more room for different shades per colorset,
                # raising it leaves more room for variance.
                min_s = 0.5 #50%
                min_v = 0.45 #45%
                max_s = 0.9
                if len(indices[colorset]) == 1:
                    max_v = 0.9
                elif len(indices[colorset]) == 2:
                    max_v = 0.84
                elif len(indices[colorset]) == 3:
                    max_v = 0.7
                elif len(indices[colorset]) == 4:
                    max_v = 0.6
                elif len(indices[colorset]) == 5:
                    max_v = 0.55
                else:
                    logger.info("ERROR: bad shade count: %d" % len(indices[colorset]))
                    return

                new_r, new_g, new_b = get_random_color(min_s, min_v, max_s, max_v)
                first_r = new_r
                first_g = new_g
                first_b = new_b
            else:
                new_r, new_g, new_b = get_different_color(first_r, first_g, first_b, colorangles[colorset])

            for color in range(len(indices[colorset])):
                shaded_r = new_r + color * math.floor((31 - new_r) / len(indices[colorset]))
                shaded_g = new_g + color * math.floor((31 - new_g) / len(indices[colorset]))
                shaded_b = new_b + color * math.floor((31 - new_b) / len(indices[colorset]))
                new_high, new_low = bytes_from_rgb(shaded_r, shaded_g, shaded_b)
                palette[mail*30+indices[colorset][color]*2 + 1] = new_high
                palette[mail*30+indices[colorset][color]*2] = new_low

# Currently only works with roms that have the asm from 
# https://github.com/Zarby89/Enemizer/blob/master/Assembly/sprite_randomizer.asm (non-AP) or
# https://github.com/ArchipelagoMW/z3randomizer/blob/main/RandSprite.asm (AP)
def apply_random_sprite_on_event(rom):
    logger = logging.getLogger('')
    write_byte(rom, 0x186381, 0x00) #enable random sprites
    # Currently set to trigger on all supported events.  Change this to limit the events
    # to: 1 (hit), 2 (enter), 4 (exit), 8 (slash), 16 (item), 32 (bonk)
    write_byte(rom, 0x18637F, 0xFF) #onevent all byte 1
    write_byte(rom, 0x186380, 0xFF) #onevent all byte 2

    sprite_list = list()
    sprite_count = 0
    for path in Path('./sprites/').rglob('*.zspr'):
        sprite_list.append(path)
        sprite_count = sprite_count + 1

    if not sprite_list:
        logger.info("ERROR: couldn't find sprites for patching.")
        return

    sprite_list_shuffled = sprite_list.copy()
    random.shuffle(sprite_list_shuffled)

    max_extended_sprites = 32
    copies_per_sprite = math.floor(max_extended_sprites / sprite_count)

    logger.info("Rainbowifying %d sprites" % sprite_count)

    index = 0
    for sprite_path in sprite_list_shuffled:
        spritename, authorname, authorshortname, sprite, palette, glove = open_zspr(sprite_path)
        # Copy the first sprite to the default sprite slot
        if (index == 0):
            shuffled_palette = palette.copy()
            shuffle_mail_palette(shuffled_palette, spritename)
            write_sprite(rom, sprite, shuffled_palette, glove,
                         0x80000,
                         0xdd308,
                         0xdedf5)
            index = index + 1

        for i in range(copies_per_sprite):
            shuffled_palette = palette.copy()
            shuffle_mail_palette(shuffled_palette, spritename)

            write_sprite(rom, sprite, shuffled_palette, glove,
                         0x300000 + (index - 1) * 0x8000,
                         0x307000 + (index - 1) * 0x8000,
                         0x307078 + (index - 1) * 0x8000)
            index = index + 1
            if (index > max_extended_sprites):
                logger.info("Done!")
                return


def main(args, romname):
    if (args.zspr_out):
        # Grab a sprite from ./sprites/
        for path in Path('./sprites').rglob('*.zspr'):
            sprite_path = path
            break
        spritename, authorname, authorshortname, sprite, palette, glove = open_zspr(sprite_path)

        if not os.path.exists('./output'):
            os.makedirs('./output')

        for i in range(args.zspr_out_count):
            shuffled_palette = palette.copy()
            shuffle_mail_palette(shuffled_palette, spritename)

            origname = os.path.basename(str(sprite_path))
            outfilename = "./output/Mailpaletteshuffled." + str(i) + "." + origname

            dump_zspr(spritename, authorname, authorshortname, sprite, shuffled_palette, glove, outfilename)

    else:
        rom = bytearray(open(romname, 'rb').read())
        apply_random_sprite_on_event(rom)
        outfilename = '%s_%s' % ('patched', os.path.basename(romname))
        with open('%s' % outfilename, 'wb') as outfile:
            outfile.write(rom)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--loglevel', default='info', const='info', nargs='?', choices=['error', 'info', 'warning', 'debug'], help='Select level of logging for output.')
    parser.add_argument('--zspr_out', action='store_true', default=False, help='Generates rainbow sprites as .zspr files in the ./output/ folder instead of patching the provided rom.')
    parser.add_argument('--zspr_out_count', type=int, default=200, help='Number of sprites to create in --zspr_out mode (default 200)')
    args, passedroms = parser.parse_known_args()

    finalrom = ""
    for passedrom in passedroms:
        finalrom = passedrom
        if not os.path.exists(passedrom):
            input('Invalid rom passed. Please run with -h to see help for further information. \nPress Enter to exit.')
            exit(1)

    # set up logger
    loglevel = {'error': logging.ERROR, 'info': logging.INFO, 'warning': logging.WARNING, 'debug': logging.DEBUG}[args.loglevel]
    logging.basicConfig(format='%(message)s', level=loglevel)

    main(args, finalrom)

