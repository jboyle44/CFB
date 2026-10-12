"""Hand-confirmed name differences between Ourlads (our depth charts) and
teamcrafters' Madden27 rosters, per team: {team_key: {our name: Madden name}}.
Only for true name differences (nicknames, shortened or full first names),
each checked as the same player on the same team. Formatting differences
(periods, accents, suffixes) are handled by normalize_name/strip_suffix and
don't belong here. Reviewed 2026-10-12."""
MADDEN27_ALIASES = {
    "cin": {"Mitch Tinsley": "Mitchell Tinsley"},
    "hou": {"Jake Hummel": "Jacob Hummel", "Nate Thomas": "Nathan Thomas"},
    "ind": {"Cam Bynum": "Camryn Bynum", "Jaylahn Tuimoloau": "JT Tuimoloau"},
    "mia": {"Josh Uche": "Joshua Uche", "Rob Beal Jr.": "Robert Beal Jr"},
    "min": {"Ben Yurosek": "Benjamin Yurosek", "Joshua Metellus": "Josh Metellus"},
    "ne": {"Andy Borregales": "Andres Borregales"},
    "phi": {"Hollywood Brown": "Marquise Brown"},
    "pit": {"Cameron Heyward": "Cam Heyward", "Gabriel Rubio": "Gabe Rubio"},
    "sea": {"Olu Oluwatimi": "Olusegun Oluwatimi"},
    "ten": {"Nicholas Singleton": "Nick Singleton"},
    "was": {"Chig Okonkwo": "Chigoziem Okonkwo"},
}
