"""Parsers for official German operational pages (no HA dependencies).

Never interpret a fetch/parse failure as proof that no incident exists.
A page redesign yields status='unknown', rather than 'normal'.
"""
from __future__ import annotations

from html.parser import HTMLParser
import re
from statistics import median


class _PlainText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "noscript"):
            self.skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip and data.strip():
            self.parts.append(data.strip())


def plain_text(html: str) -> str:
    parser = _PlainText()
    parser.feed(html)
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def parse_gas(html: str) -> dict:
    text = plain_text(html)
    match = re.search(
        r"Füllstände der Speicher in Deutschland liegen derzeit bei\s*"
        r"(\d{1,3}(?:[,.]\d+)?)\s*%",
        text, re.IGNORECASE,
    )
    if not match:
        return {"status": "unknown", "detail": "Gas storage percentage not found"}
    level = float(match.group(1).replace(",", "."))
    if not 0 <= level <= 100:
        return {"status": "unknown", "detail": "Invalid gas percentage"}
    amount = re.search(r"\(\s*(\d{1,4}(?:[,.]\d+)?)\s*TWh\s*\)", text[match.start():match.end()+50], re.I)
    early = "Frühwarnstufe" in text
    stable_supply = bool(re.search(r"Gasversorgung in Deutschland ist stabil|Versorgungssicherheit ist gewährleistet", text, re.I))
    low_comparison = bool(re.search(r"deutlich niedriger als in den Vergleichszeiträumen", text, re.I))
    confirmed_shortage = bool(re.search(
        r"Versorgungssicherheit ist nicht gewährleistet|Notfallstufe.*?ausgerufen|"
        r"Gasversorgung in Deutschland ist nicht stabil", text, re.I,
    ))
    imports_stable = bool(re.search(r"Gasimporte sind stabil", text, re.I))
    assessed = bool(stable_supply or confirmed_shortage)
    if not assessed:
        return {"status": "unknown", "detail": "Gas supply assessment could not be read", "storage_percent": level}
    return {
        "status": "crisis" if confirmed_shortage else "stable" if stable_supply else "unknown",
        "storage_percent": level,
        "storage_twh": float(amount.group(1).replace(",", ".")) if amount else None,
        "early_warning": early,
        "imports_stable": imports_stable,
        "lower_than_previous_years": low_comparison,
        "detail": "Official gas supply assessment",
    }


def parse_water(html: str) -> dict:
    text = plain_text(html)
    if "Aktuelle Störungen" not in text:
        return {"status": "unknown", "detail": "Water incident section not found"}
    section = text.rsplit("Aktuelle Störungen", 1)[-1].split("Was soll ich tun", 1)[0].strip()
    if re.search(r"Im Moment existieren keine Störungsmeldungen", section, re.I):
        return {"status": "normal", "detail": "Aucune perturbation publiée", "area": ""}
    if not section or len(section) < 15 or section.lower().startswith("erste hilfe"):
        return {"status": "unknown", "detail": "Water status could not be parsed"}
    if not re.search(r"Rohrbruch|Störung|Wasserversorgung|Wasser|Unterbrechung|Versorgung", section, re.I):
        return {"status": "unknown", "detail": "No recognized water outage content"}
    areas = re.findall(r"\b(?:Marmstorf|Harburg|Westerheide|Koboldweg|Handweg)\b", section, re.I)
    return {
        "status": "active",
        "detail": section[:900],
        "area": ", ".join(dict.fromkeys(areas)),
        "local": bool(areas),
    }


def parse_electricity(html: str) -> dict:
    text = plain_text(html)
    if "Aktuelle Stromstörungen" not in text:
        return {"status": "unknown", "detail": "Electricity incident section not found"}
    section = text.rsplit("Aktuelle Stromstörungen", 1)[-1].split("Störungen der öffentlichen Beleuchtung", 1)[0].strip()
    if re.search(r"Keine Störungen|keine größeren Störungen im Versorgungsgebiet bekannt", section, re.I):
        return {"status": "normal", "detail": "Aucune panne majeure publiée", "area": ""}
    if len(section) < 15 or not re.search(r"Störung|Stromausfall|Versorgungsunterbrechung|Ausfall", section, re.I):
        return {"status": "unknown", "detail": "Electricity status could not be parsed"}
    areas = re.findall(r"\b(?:Marmstorf|Harburg|Koboldweg)\b", section, re.I)
    return {
        "status": "active",
        "detail": section[:900],
        "area": ", ".join(dict.fromkeys(areas)),
        "local": bool(areas),
    }


def fuel_medians(prices: dict[str, list[float]]) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for fuel in ("diesel", "e5", "e10"):
        values = [float(x) for x in prices.get(fuel, []) if 0.5 <= float(x) <= 4.0]
        result[fuel] = round(median(values), 3) if values else None
    return result
