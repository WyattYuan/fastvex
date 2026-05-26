from __future__ import annotations

DEFAULT_CONFIG_TEXT = """# fastvex configuration
# Common commands:
#   fastvex validate
#   fastvex show
#   fastvex deploy --slots 1,2 -y
schemaVersion: 2

robot:
  name: Sparkle
  team: HITSZ1

programName:
  template: "{profile}-{route}-{robot}"

alliances:
  red:
    routes:
      left:
        buildArgs:
          ROUTE: 1
      right:
        buildArgs:
          ROUTE: 2
  blue:
    routes:
      left:
        buildArgs:
          ROUTE: 1
      right:
        buildArgs:
          ROUTE: 2
  skill:
    routes:
      main:
        buildArgs:
          ROUTE: 0

profiles:
  redComp:
    alliance: red
    buildArgs:
      MODE: RED_COMP
  blueComp:
    alliance: blue
    buildArgs:
      MODE: BLUE_COMP
  skillComp:
    alliance: skill
    buildArgs:
      MODE: SKILL_COMP
  redDebug:
    alliance: red
    buildArgs:
      MODE: RED_DEBUG
  blueDebug:
    alliance: blue
    buildArgs:
      MODE: BLUE_DEBUG

slots:
  1:
    profile: redComp
    route: left
  2:
    profile: blueComp
    route: right
  3:
    profile: skillComp
    route: main
  4:
    profile: redDebug
    route: left
  5:
    profile: blueDebug
    route: right
  6: empty
  7: empty
  8: empty

slotGroups:
  all: [1, 2, 3, 4, 5, 6, 7, 8]
"""

DEFAULT_SETTINGS_TEXT = """{
  "historyRetentionCount": 10
}
"""

DEFAULT_LOCAL_GITIGNORE_TEXT = """*
!.gitignore
"""
