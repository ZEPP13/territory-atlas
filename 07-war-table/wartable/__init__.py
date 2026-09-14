"""War table data layers: registry, signals, logbook. See 00-framework/WAR-TABLE.md."""
import os

PKG = os.path.dirname(os.path.abspath(__file__))
WAR = os.path.dirname(PKG)
ROOT = os.path.dirname(WAR)
SCHEMAS = os.path.join(WAR, "schemas")
CONFIG = os.path.join(WAR, "config")
DIST = os.path.join(WAR, "dist")
DATA = os.path.join(ROOT, "02-data")
