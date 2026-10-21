#!/usr/bin/env python3
"""Prospective research-only source capture; no formal signal."""
import datetime as dt
from zoneinfo import ZoneInfo

def preopen(t):
    local=t.astimezone(ZoneInfo("Asia/Shanghai"))
    return local.weekday()<5 and dt.time(8,30)<=local.time().replace(tzinfo=None)<dt.time(9,20)
