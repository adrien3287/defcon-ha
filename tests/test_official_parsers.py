"""Offline, deterministic tests for parsing real operator status formats."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "defcon_ha"))
from official_parsers import parse_gas, parse_water, parse_electricity, fuel_medians


class OfficialSourcesParsersTest(unittest.TestCase):
    def test_gas_stable_low(self):
        html = """<html><body><h1>Aktuelle Lage</h1><p>Die Füllstände der Speicher
        in Deutschland liegen derzeit bei 61 % (151 TWh). Sie sind deutlich niedriger
        als in den Vergleichszeiträumen vergangener Jahre.</p>
        <p>Die Gasimporte sind stabil.</p>
        <p>Die Gasversorgung in Deutschland ist stabil.
        Die Versorgungssicherheit ist gewährleistet. Frühwarnstufe.</p>
        </body></html>"""
        data = parse_gas(html)
        self.assertEqual(data["status"], "stable")
        self.assertEqual(data["storage_percent"], 61)
        self.assertEqual(data["storage_twh"], 151)
        self.assertTrue(data["imports_stable"])
        self.assertTrue(data["lower_than_previous_years"])

    def test_gas_missing_does_not_claim_normal(self):
        self.assertEqual(parse_gas("<html>Keine Daten</html>")["status"], "unknown")

    def test_water_no_incident(self):
        html = """<html><nav>Aktuelle Störungen</nav><h2>Aktuelle Störungen</h2>
        Im Moment existieren keine Störungsmeldungen.
        <h2>Was soll ich tun?</h2></html>"""
        self.assertEqual(parse_water(html)["status"], "normal")

    def test_water_local_incident(self):
        html = """<h2>Aktuelle Störungen</h2>
        Rohrbruch in Hamburg-Marmstorf, Westerheide 1-12. Wasserversorgung unterbrochen.
        <h2>Was soll ich tun?</h2>"""
        result = parse_water(html)
        self.assertEqual(result["status"], "active")
        self.assertTrue(result["local"])

    def test_water_unknown(self):
        self.assertEqual(parse_water("<h2>Service</h2>")["status"], "unknown")

    def test_power_no_large_incident(self):
        html = """<h2>Aktuelle Stromstörungen</h2>Keine Störungen!
        Zurzeit sind uns keine größeren Störungen im Versorgungsgebiet bekannt.
        <h2>Störungen der öffentlichen Beleuchtung</h2>"""
        self.assertEqual(parse_electricity(html)["status"], "normal")

    def test_power_outage_harburg(self):
        html = """<h2>Aktuelle Stromstörungen</h2>
        Stromausfall in Hamburg-Harburg, Versorgungsunterbrechung.
        <h2>Störungen der öffentlichen Beleuchtung</h2>"""
        result = parse_electricity(html)
        self.assertEqual(result["status"], "active")
        self.assertTrue(result["local"])

    def test_fuel_median_ignores_outlier(self):
        self.assertEqual(fuel_medians({"diesel": [1.72, 1.71, 1.73, 5.0]})["diesel"], 1.72)


if __name__ == "__main__":
    unittest.main()
