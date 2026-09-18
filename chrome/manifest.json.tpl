{
  "manifest_version": 3,
  "name": "Omarchy Theme",
  "version": "1.0",
  "description": "Chrome theme generated from the active Omarchy theme (colors.toml). Loaded via --load-extension in ~/.config/chrome-flags.conf.",
  "theme": {
    "colors": {
      "frame": [{{ dark_background_rgb }}],
      "frame_inactive": [{{ dark_background_rgb }}],
      "frame_incognito": [{{ darker_background_rgb }}],
      "frame_incognito_inactive": [{{ darker_background_rgb }}],
      "toolbar": [{{ background_rgb }}],
      "toolbar_button_icon": [{{ foreground_rgb }}],
      "tab_text": [{{ bright_foreground_rgb }}],
      "tab_background_text": [{{ dark_foreground_rgb }}],
      "tab_background_text_inactive": [{{ dark_foreground_rgb }}],
      "bookmark_text": [{{ foreground_rgb }}],
      "omnibox_background": [{{ lighter_background_rgb }}],
      "omnibox_text": [{{ bright_foreground_rgb }}],
      "button_background": [{{ background_rgb }}],
      "ntp_background": [{{ background_rgb }}],
      "ntp_text": [{{ foreground_rgb }}],
      "ntp_link": [{{ bright_blue_rgb }}],
      "ntp_section": [{{ lighter_background_rgb }}],
      "ntp_section_text": [{{ foreground_rgb }}],
      "ntp_section_link": [{{ bright_blue_rgb }}]
    }
  }
}
