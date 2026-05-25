from __future__ import annotations

DEFAULT_CONFIG_TEXT = """# fastvex configuration
# Common commands:
#   fastvex validate
#   fastvex show
#   fastvex upload --slots 1,2 -y
schemaVersion: 1
historyRetentionCount: 10
defaults:
  robotName: Sparkle
  port: ""
  nameTemplate: "{modeCamel}{routeSuffix}-{robotName}"
roles:
  red-comp:
    mode: RED_COMP
    routeSet: red
    label: Red Comp
    enabled: true
  red-debug:
    mode: RED_DEBUG
    routeSet: red
    label: Red Debug
    enabled: true
  blue-comp:
    mode: BLUE_COMP
    routeSet: blue
    label: Blue Comp
    enabled: true
  blue-debug:
    mode: BLUE_DEBUG
    routeSet: blue
    label: Blue Debug
    enabled: true
  skill-comp:
    mode: SKILL_COMP
    routeSet: skill
    label: Skill Comp
    enabled: true
  skill-debug:
    mode: SKILL_DEBUG
    routeSet: skill
    label: Skill Debug
    enabled: true
routes:
  red:
    r0:
      route: 0
      routeName: Default
      label: Default
      enabled: true
  blue:
    r0:
      route: 0
      routeName: Default
      label: Default
      enabled: true
  skill:
    r0:
      route: 0
      routeName: Default
      label: Default
      enabled: true
activeRoute:
  red: r0
  blue: r0
  skill: r0
slots:
  1: { role: red-debug, route: r0 }
  2: { role: blue-debug, route: r0 }
  3: { role: red-comp, route: r0 }
  4: { role: blue-comp, route: r0 }
  5: { role: skill-debug, route: r0 }
  6: { role: skill-comp, route: r0 }
  7: { role: red-debug, route: r0 }
  8: { role: blue-debug, route: r0 }
groups:
  all-enabled: [1, 2, 3, 4, 5, 6, 7, 8]
"""
