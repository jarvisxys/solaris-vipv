"""Independent sun-position reference for E1: the NOAA Solar Calculator algorithm.

This is NOAA GML's published solar calculator (spreadsheet NOAA_Solar_Calculations_day.xls
and solcalc), after Meeus, "Astronomical Algorithms". It shares no code with pvlib's NREL
SPA, which is why E1 uses it for the Phoenix spot checks.
"""

import math


def julian_day(year, month, day, hour_utc):
    if month <= 2:
        year, month = year - 1, month + 12
    a = year // 100
    b = 2 - a + a // 4
    jd = math.floor(365.25 * (year + 4716)) + math.floor(30.6001 * (month + 1)) + day + b - 1524.5
    return jd + hour_utc / 24.0


def noaa_sun(year, month, day, hour_local, tz_hours, lat, lon):
    """(apparent elevation, azimuth from true north), deg, as NOAA's calculator returns them.
    ``hour_local`` is decimal local standard time; ``tz_hours`` is the UTC offset (-7)."""
    jd = julian_day(year, month, day, hour_local - tz_hours)
    t = (jd - 2451545.0) / 36525.0
    l0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360.0
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    mr = math.radians(m)
    c = (
        math.sin(mr) * (1.914602 - t * (0.004817 + 0.000014 * t))
        + math.sin(2 * mr) * (0.019993 - 0.000101 * t)
        + math.sin(3 * mr) * 0.000289
    )
    true_long = l0 + c
    omega = 125.04 - 1934.136 * t
    app_long = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    seconds = 21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))
    obliq = 23.0 + (26.0 + seconds / 60.0) / 60.0 + 0.00256 * math.cos(math.radians(omega))
    decl = math.degrees(math.asin(math.sin(math.radians(obliq)) * math.sin(math.radians(app_long))))
    y = math.tan(math.radians(obliq / 2)) ** 2
    l0r = math.radians(l0)
    eq_time = 4 * math.degrees(
        y * math.sin(2 * l0r)
        - 2 * e * math.sin(mr)
        + 4 * e * y * math.sin(mr) * math.cos(2 * l0r)
        - 0.5 * y * y * math.sin(4 * l0r)
        - 1.25 * e * e * math.sin(2 * mr)
    )
    tst = (hour_local * 60.0 + eq_time + 4 * lon - 60 * tz_hours) % 1440.0
    ha = tst / 4 - 180 if tst / 4 >= 0 else tst / 4 + 180
    lat_r, dec_r, ha_r = math.radians(lat), math.radians(decl), math.radians(ha)
    cos_z = math.sin(lat_r) * math.sin(dec_r) + math.cos(lat_r) * math.cos(dec_r) * math.cos(ha_r)
    zen = math.degrees(math.acos(max(-1.0, min(1.0, cos_z))))
    el = 90.0 - zen
    if el > 85:
        refr = 0.0
    elif el > 5:
        te = math.tan(math.radians(el))
        refr = 58.1 / te - 0.07 / te**3 + 0.000086 / te**5
    elif el > -0.575:
        refr = 1735 + el * (-518.2 + el * (103.4 + el * (-12.79 + el * 0.711)))
    else:
        refr = -20.772 / math.tan(math.radians(el))
    el_app = el + refr / 3600.0
    az_num = math.sin(lat_r) * math.cos(math.radians(zen)) - math.sin(dec_r)
    az = math.degrees(
        math.acos(max(-1.0, min(1.0, az_num / (math.cos(lat_r) * math.sin(math.radians(zen))))))
    )
    az = (az + 180) % 360 if ha > 0 else (540 - az) % 360
    return el_app, az
