# twitch-bot

This is a chatbot I use for my stream at https://www.twitch.tv/jmal116

## How do I use the channel point redemptions?

### Text To Speech

Just put in some text and the bot will read it.

I do have the ability to skip redemptions with blatantly offensive text. If you make me use it, you will be banned.

### Change Mega Health/Energy Display

Changes the settings for how the additional resource row for mega health and mega energy are displayed. You can modify the horizontal and veritcal placement, as well as the size of the cells.

You can see the current values of these settings (as of the start of this stream) in [current_rando_settings.txt](/current_rando_settings.txt).

Expected input format is 3 numbers, separated by commas. These values modify the settings `Temp Row Spacing`, `Temp Row Horizontal Offset`, and `Temp Row Scale`. For example, the input `0.8, 0, 0.7` would set the vertical spacing of the temp row to 0.8, the horizontal offset to 0, and the scale of the cells to 0.7.

### Change Pickup Background Color

Changes the color of the box surrounding the pickup names every time I get a pickup. This applies to pickups that I find for my own game (which is most of them, unless I'm playing a multiworld). You can specify an RGB value along with an alpha value for transparency.

You can see the current color of the box (as of the start of this stream) in [current_rando_settings.txt](/current_rando_settings.txt).

Expected input format is a color, either as a hex code or as separate numbers for RBG. You can use a color picker to easily get these codes, such as the one at https://htmlcolorcodes.com/color-picker/. You can optionally supply an alpha component. Examples of valid input:
* `FFFFFF` - Full white background, probably making all the pickup names completely unreadable
* `FFFFFF00` - Full white background, but with 0% opacity
* `#FF0000` - Full red background
* `0, 255, 0` - Full green background
* `0, 0, 255, 125` - Full blue background, with ~50% opacity

### Change Multiworld Pickup Background Color

This functions identically to the previous reward, except it only changes the background color for other player's pickups in a multiworld game.

I sometimes play Ori in APs off stream, so this reward will probably just mess with me at a later date but it's unlikely to come up very frequently on stream.

### Add an experience name

Many experience pickups do not say "experience" as the pickup name, instead they choose a random name from a list. This reward adds an entry to that list, which I will never manually remove. At some point in the future you will see this experience name pop up in my game without warning, and it will probably stay there forever unless someone else decides they really don't like it and chooses to remove it themselves.

The current list of experience names (as of the start of this stream) is in [current_exp_names.txt](/current_exp_names.txt).

### Remove an experience name

If someone really made you mad, you can remove the expereience name they added to the list of random experience names from the previous reward.

The current list of experience names (as of the start of this stream) is in [current_exp_names.txt](/current_exp_names.txt).