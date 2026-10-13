#!/usr/bin/env python3
# Gerz Clock weather: Open-Meteo -> native Gerz/GisMeteo informer XML (Gomel 33041)
import json, urllib.request, datetime, sys

LAT, LON = 52.4334, 30.9900
NUMBER, CITY_RU, COUNTRY_RU = "33041", "Гомель", "Беларусь"

def fetch():
    url = ("https://api.open-meteo.com/v1/forecast?latitude=%.4f&longitude=%.4f"
           "&hourly=temperature_2m,apparent_temperature,relative_humidity_2m,pressure_msl,"
           "cloud_cover,precipitation_probability,precipitation,precipitation_type,weather_code,"
           "windspeed_10m,winddirection_10m"
           "&forecast_days=4&timezone=Europe%%2FMinsk&wind_speed_unit=ms" % (LAT, LON))
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GerzClock/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            if attempt == 4:
                raise
            import time; time.sleep(20 * (attempt + 1))

def tod_code(h):
    if 0 <= h < 6:  return 3
    if 6 <= h < 12: return 2
    if 12 <= h < 18:return 1
    return 0

def wdir_code(deg, speed):
    if speed < 0.6: return 0
    s = int(((deg + 22.5) % 360) // 45)
    return 8 - s

def cloud_code(pct):
    if pct < 20:  return 0
    if pct < 55:  return 1
    if pct < 85:  return 2
    return 3

def precip_code(code, mm, prob):
    if code in (95, 96, 99): return 8
    if code in (71, 73, 75, 77, 85, 86, 66, 64, 62):
        return 7 if code in (75, 77, 86) else 6
    if code in (65, 67, 82, 81) or mm >= 3: return 5
    if code in (61, 63, 80, 55, 57, 53) or mm > 0.1: return 4
    return 10

def build():
    d = fetch(); h = d["hourly"]; n = len(h["time"])
    days = {}
    for i in range(n):
        dt = datetime.datetime.fromisoformat(h["time"][i])
        days.setdefault((dt.date(), tod_code(dt.hour)), []).append(i)
    out = []
    for (d_, period), idxs in sorted(days.items()):
        def agg(k, f):
            v = [h[k][i] for i in idxs if h[k][i] is not None]
            return f(v) if v else 0
        a  = lambda k: agg(k, lambda v: sum(v) / len(v))
        mn = lambda k: agg(k, min)
        mx = lambda k: agg(k, max)
        hh = int(datetime.datetime.fromisoformat(h["time"][idxs[len(idxs)//2]]).hour)
        out.append(dict(
            date=d_.day, month=d_.month, year=d_.year, hour=hh, tod=period,
            tmin=round(mn("temperature_2m")), tmax=round(mx("temperature_2m")),
            pmin=round(mn("pressure_msl") * 0.750062), pmax=round(mx("pressure_msl") * 0.750062),
            wmin=round(mn("relative_humidity_2m")), wmax=round(mx("relative_humidity_2m")),
            vmin=round(mn("windspeed_10m")), vmax=round(mx("windspeed_10m")),
            hmin=round(mn("apparent_temperature")), hmax=round(mx("apparent_temperature")),
            dirn=wdir_code(a("winddirection_10m"), a("windspeed_10m")),
            cloud=cloud_code(a("cloud_cover")),
            cloud_pct=round(a("cloud_cover")),
            precip=precip_code(max(h["weather_code"][i] for i in idxs),
                               mx("precipitation"), mx("precipitation_probability")),
            prob=mx("precipitation_probability"),
        ))
    return out

TOD2INF = {3: 1, 2: 2, 1: 3, 0: 4}
WDIR_NAMES = ["С", "С-В", "В", "Ю-В", "Ю", "Ю-З", "З", "С-З"]

def write_informer_xml(path):
    now = datetime.datetime.now()
    feats = build()
    by_day = {}
    for f in feats:
        by_day.setdefault((f["year"], f["month"], f["date"]), []).append(f)
    def phen_block(y, m, d):
        dstr = "%02d.%02d.%d" % (d, m, y)
        L = ['<PHENOMENONS d="%s">' % dstr]
        for f in sorted(by_day[(y, m, d)], key=lambda x: x["tod"]):
            L.append('<PHENOMEN d="%s" t="%d" s="0">' % (dstr, TOD2INF[f["tod"]]))
            L.append("<T>%d</T><Tmin>%d</Tmin><Tmax>%d</Tmax>" % (round((f["tmin"]+f["tmax"])/2), f["tmin"], f["tmax"]))
            L.append("<P>%d</P><Pmin>%d</Pmin><Pmax>%d</Pmax>" % (round((f["pmin"]+f["pmax"])/2), f["pmin"], f["pmax"]))
            L.append("<W>%d</W><Wmin>%d</Wmin><Wmax>%d</Wmax>" % (round((f["vmin"]+f["vmax"])/2), f["vmin"], f["vmax"]))
            L.append("<WMP>%d</WMP>" % round((f["vmin"]+f["vmax"])/2*3.6))
            L.append("<S>%d</S>" % f["cloud_pct"])
            L.append("<Pp>%d</Pp>" % f["precip"])
            L.append("<DD>%s</DD>" % ("Шт." if f["dirn"] == 8 else WDIR_NAMES[(8 - f["dirn"]) % 8]))
            L.append("<Day>%d</Day><Month>%d</Month><Year>%d</Year><Hour>%d</Hour><Minute>0</Minute>" % (f["date"], f["month"], f["year"], f["hour"]))
            L.append("</PHENOMEN>")
        L.append("</PHENOMENONS>")
        return "\n".join(L)
    today = (now.year, now.month, now.day)
    tom = (now + datetime.timedelta(days=1)).date()
    tom = (tom.year, tom.month, tom.day)
    body = []
    body.append('<?xml version="1.0" encoding="windows-1251"?>')
    body.append("<GETWEATHER>")
    body.append("<MM>%02d</MM><DD>%02d</DD><YY>%d</YY>" % (now.month, now.day, now.year))
    body.append('<City code="%s" locale="ru" latitude="52.43" longitude="30.99" title="%s" country="%s" region="Гомельская обл.">' % (NUMBER, CITY_RU, COUNTRY_RU))
    body.append('<LocalTime timezone="3"><Year>%d</Year><Month>%d</Month><Day>%d</Day><Hour>%d</Hour><Minute>%d</Minute></LocalTime>' % (now.year, now.month, now.day, now.hour, now.minute))
    if today in by_day:
        body.append("<TODAY>"); body.append(phen_block(*today)); body.append("</TODAY>")
    if tom in by_day:
        body.append("<TOMORROW>"); body.append(phen_block(*tom)); body.append("</TOMORROW>")
    body.append("</City>")
    body.append("</GETWEATHER>")
    open(path, "w", encoding="windows-1251").write("\n".join(body))
    return path

if __name__ == "__main__":
    import os
    write_informer_xml("33041_1.xml")
    empty = '<?xml version="1.0" encoding="windows-1251"?><items></items>'
    open("a.xml", "w", encoding="windows-1251").write(empty)
    open("c.xml", "w", encoding="windows-1251").write(empty)
    print("ok 33041_1.xml")
